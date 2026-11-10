from __future__ import annotations

import re

import httpx
import pypdfium2 as pdfium

from adapters.sec_client import SecClient
from domain.models import AppError

_EPIC = re.compile(r"[A-Z]{3}\d{7}")


def load_booths(sec: SecClient, job: dict) -> list[dict]:
    if job["body_type"] == "gram_panchayat":
        return sec.gram_booths(job["district_id"], job["prakhand_id"], job["body_id"])
    np_id = sec.nagar_id(job["district_id"], job["body_name"])
    if not np_id:
        return []
    return sec.nagar_booths(np_id)


def single_booth_by_ward(booths: list[dict]) -> dict[int, str]:
    grouped: dict[int, list[str]] = {}
    for booth in booths:
        grouped.setdefault(int(booth["ward_no"]), []).append(str(booth["booth_no"]))
    return {ward: numbers[0] for ward, numbers in grouped.items() if len(numbers) == 1}


def wards_with_pdfs(booths: list[dict]) -> list[dict]:
    singles = single_booth_by_ward(booths)
    grouped: dict[int, list[dict]] = {}
    for booth in booths:
        ward = int(booth["ward_no"])
        if ward in singles or not booth.get("pdf_url"):
            continue
        grouped.setdefault(ward, []).append(
            {"booth_no": str(booth["booth_no"]), "pdf_url": str(booth["pdf_url"])}
        )
    return [{"ward_no": ward, "booths": items} for ward, items in sorted(grouped.items())]


def epics_in_text(text: str) -> set[str]:
    return set(_EPIC.findall(text.upper()))


def serial_span(text: str) -> tuple[int, int] | None:
    numbers = sorted({int(line.strip()) for line in text.splitlines() if line.strip().isdigit() and int(line.strip()) > 0})
    if len(numbers) < 2:
        return None
    start, end = numbers[0], numbers[-1]
    if end - start + 1 != len(numbers):
        return None
    return start, end


def ranges_overlap(spans: list[tuple[int, int]]) -> bool:
    ordered = sorted(spans)
    return any(ordered[index][0] <= ordered[index - 1][1] for index in range(1, len(ordered)))


def pdf_text(pdf: bytes) -> str:
    document = pdfium.PdfDocument(pdf)
    try:
        return "\n".join(page.get_textpage().get_text_bounded() for page in document)
    finally:
        document.close()


def apply_ward_pdfs(rolls, job: dict, ward_no: int, booths: list[dict]) -> None:
    parsed: list[tuple[str, str]] = []
    for booth in booths:
        parsed.append((str(booth["booth_no"]), pdf_text(download_pdf(str(booth["pdf_url"])))))
    for booth_no, text in parsed:
        found = epics_in_text(text)
        if found:
            rolls.assign_booth_epics(job, ward_no, booth_no, found)
    spans: list[tuple[str, tuple[int, int]]] = []
    for booth_no, text in parsed:
        span = serial_span(text)
        if span is None:
            return
        spans.append((booth_no, span))
    if ranges_overlap([span for _, span in spans]):
        return
    for booth_no, (first, last) in spans:
        rolls.assign_booth_serials(job, ward_no, booth_no, first, last)


def fill_body(sec: SecClient, rolls, job: dict) -> dict:
    booths = load_booths(sec, job)
    singles = single_booth_by_ward(booths)
    for ward_no, booth_no in singles.items():
        rolls.assign_booth_ward(job, ward_no, booth_no)
    groups = wards_with_pdfs(booths)
    for group in groups:
        apply_ward_pdfs(rolls, job, int(group["ward_no"]), group["booths"])
    return {
        "body_name": job["body_name"],
        "booths": len(booths),
        "single_wards": len(singles),
        "split_wards": len(groups),
    }


def download_pdf(url: str) -> bytes:
    try:
        response = httpx.get(url, timeout=90, follow_redirects=True, headers={"User-Agent": "PsAnaRollIngest/1.0"})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AppError(f"Booth PDF download failed: {exc}", 502) from exc
    if not response.content.startswith(b"%PDF"):
        raise AppError("Booth file is not a PDF", 502)
    return response.content
