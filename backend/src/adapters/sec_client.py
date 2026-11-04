from __future__ import annotations

import html
import json
import re
from urllib.parse import urljoin

import httpx

from config.sources import SEC_VOTER_ROLL_URL
from domain.models import AppError, District, Prakhand, RollLink

_DISTRICT_BLOCK = re.compile(
    r'id="ddlDistrict"(.*?)id="ddlBlock"',
    re.S,
)
_OPTION = re.compile(r'<option value="(\d+)">([^<]+)</option>')
_WARD_NO = re.compile(r"(\d+)")


class SecClient:
    def __init__(self, base_url: str = SEC_VOTER_ROLL_URL, timeout: float = 40) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def districts(self) -> list[District]:
        return parse_district_html(self._get_text(self.base_url))

    def prakhands(self, district_id: str) -> list[Prakhand]:
        rows = self._handler("GetBlocks", {"districtId": district_id})
        return [Prakhand(str(row["i"]), str(row["n"]), district_id) for row in rows]

    def panchayats(self, district_id: str, prakhand_id: str) -> list[dict]:
        rows = self._handler(
            "GetPanchayats",
            {"districtId": district_id, "blockId": prakhand_id},
        )
        return [{"id": str(row["i"]), "name": str(row["n"])} for row in rows]

    def roll_links(self, district_id: str, prakhand_id: str, panchayat_id: str) -> list[RollLink]:
        phases = self._handler(
            "GetPhases",
            {
                "districtId": district_id,
                "blockId": prakhand_id,
                "panchayatId": panchayat_id,
                "ward": "",
            },
        )
        if not phases:
            raise AppError("SEC returned no roll phase for this panchayat", 404)
        phase = _choose_phase(phases)
        direct = self._details(district_id, prakhand_id, panchayat_id, "", phase["i"])
        rows = direct or self._details_by_ward(district_id, prakhand_id, panchayat_id, phase["i"])
        links: list[RollLink] = []
        seen: set[str] = set()
        for row in rows:
            url = str(row.get("PDFPath") or row.get("pdfPath") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            ward = _int_or_none(row.get("WardID") or row.get("wardId"))
            label = str(row.get("DocumentType") or row.get("documentType") or "roll")
            links.append(RollLink(url, ward, label))
        if not links:
            raise AppError("SEC returned no PDF for this panchayat", 404)
        return links

    def _details_by_ward(self, district_id: str, prakhand_id: str, panchayat_id: str, phase_id: str) -> list[dict]:
        wards = self._handler("GetWards", {"panchayatId": panchayat_id})
        rows: list[dict] = []
        for ward in wards:
            ward_no = ward.get("w") or ward.get("i")
            rows.extend(self._details(district_id, prakhand_id, panchayat_id, ward_no, phase_id))
        return rows

    def _details(self, district_id: str, prakhand_id: str, panchayat_id: str, ward: object, phase_id: object) -> list[dict]:
        return self._handler(
            "GetVoterRollDetails",
            {
                "districtId": district_id,
                "blockId": prakhand_id,
                "panchayatId": panchayat_id,
                "ward": ward,
                "phase": phase_id,
            },
        )

    def _handler(self, name: str, params: dict) -> list[dict]:
        response = self._request("GET", self.base_url, params={"handler": name, **params})
        return _as_rows(response.json() if response.content else [])

    def _get_text(self, url: str) -> str:
        return self._request("GET", url).text

    def _request(self, method: str, url: str, params: dict | None = None) -> httpx.Response:
        try:
            response = httpx.request(
                method,
                url,
                params=params,
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "PsAnaRollIngest/1.0"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(f"SEC request failed: {exc}", 502) from exc
        return response


def parse_district_html(page: str) -> list[District]:
    match = _DISTRICT_BLOCK.search(page)
    block = match.group(1) if match else page
    found: list[District] = []
    for value, name in _OPTION.findall(block):
        label = html.unescape(name).strip()
        if label and "select" not in label.lower():
            found.append(District(value, label))
    if not found:
        raise AppError("SEC district list was empty", 502)
    return found


def parse_nagar_page(page_html: str, page_url: str, body_name: str) -> list[RollLink]:
    wanted = body_name.casefold().strip()
    links: list[RollLink] = []
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", page_html, flags=re.I | re.S)
    for row in rows:
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        if len(cells) < 3:
            continue
        name = re.sub(r"<[^>]+>", "", cells[1])
        name = html.unescape(name).strip()
        if name.casefold() != wanted:
            continue
        href = re.search(r'href="([^"]+)"', cells[2], flags=re.I)
        label = re.sub(r"<[^>]+>", " ", cells[2])
        label = html.unescape(re.sub(r"\s+", " ", label)).strip()
        if not href or ".pdf" not in href.group(1).lower():
            continue
        url = urljoin(page_url, href.group(1).strip())
        ward_match = _WARD_NO.search(label)
        ward_no = int(ward_match.group(1)) if ward_match else None
        links.append(RollLink(url, ward_no, label))
    return links


def _choose_phase(phases: list[dict]) -> dict:
    for phase in phases:
        name = str(phase.get("n") or "")
        if "अंतिम" in name or "final" in name.casefold():
            return phase
    return phases[-1]


def _as_rows(payload: object) -> list[dict]:
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict):
        for key in ("data", "voterRolls", "result"):
            if key in payload:
                payload = payload[key]
                break
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, list):
        raise AppError("Unexpected response from SEC", 502)
    return [row for row in payload if isinstance(row, dict)]


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None
