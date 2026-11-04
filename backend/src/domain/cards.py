from __future__ import annotations

import re

from domain.models import VoterCard

_RELATION = ("पिता", "पति", "माता", "अन्य")


def clean_voter(raw: dict) -> VoterCard | None:
    serial = _int(raw.get("serial"))
    name = _text(raw.get("name"))
    if serial is None or not name:
        return None
    epic = _text(raw.get("epic"))
    if epic and epic.upper() in {"NA", "N/A", "-"}:
        epic = None
    if epic:
        epic = epic.upper()
    return VoterCard(
        serial=serial,
        epic=epic,
        name=name,
        relation=_relation(raw.get("relation")),
        relation_name=_text(raw.get("relation_name")),
        house_no=_text(raw.get("house_no")),
        age=_text(raw.get("age")),
        gender=_text(raw.get("gender")),
        assembly_ref=_text(raw.get("assembly_ref")) or None,
    )


def clean_page(payload: dict) -> dict:
    voters: list[VoterCard] = []
    seen: set[int] = set()
    for item in payload.get("voters") or []:
        if not isinstance(item, dict):
            continue
        card = clean_voter(item)
        if card is None or card.serial in seen:
            continue
        seen.add(card.serial)
        voters.append(card)
    kind = _text(payload.get("page_kind")).lower()
    if kind not in {"cover", "voters"}:
        kind = "voters" if voters else "cover"
    return {
        "page_kind": kind,
        "ward_no": _int(payload.get("ward_no")),
        "part_no": _int(payload.get("part_no")),
        "male_count": _int(payload.get("male_count")),
        "female_count": _int(payload.get("female_count")),
        "total_count": _int(payload.get("total_count")),
        "voters": voters,
    }


def _relation(value: object) -> str:
    text = _text(value).replace(" ", "")
    for label in _RELATION:
        if label in text:
            return label
    return _text(value)


def _text(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _int(value: object) -> int | None:
    if value is None or value == "":
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    return int(match.group(0))
