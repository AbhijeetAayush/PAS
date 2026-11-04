"""Marks a person adds onto a printed voter row.

Religion, caste, and occupation are chosen. Category is not chosen: it follows
the caste. The mark is stored beside the roll, keyed the same way as the
BigQuery insert id, so a later read of the PDF does not wipe it.
"""

from __future__ import annotations

import re

from adapters.roll_store import string_param
from domain.models import AppError
from services.age import AGE_SQL, age_labels, age_where
from services.name_search import column_search

RELIGIONS = ("Hindu", "Muslim", "Christian", "Sikh")

CASTES = (
    ("Yadav", "BC-II"),
    ("Dusadh / Paswan", "SC"),
    ("Chamar / Ravidas / Mochi", "SC"),
    ("Kushwaha / Koeri", "BC-II"),
    ("Sheikh", "GEN"),
    ("Brahmin", "GEN"),
    ("Momin / Ansari", "EBC"),
    ("Rajput", "GEN"),
    ("Musahar", "SC"),
    ("Kurmi", "BC-II"),
    ("Bhumihar", "GEN"),
    ("Teli", "BC-II"),
    ("Mallah", "EBC"),
    ("Bania / Vaishya", "BC-II"),
    ("Kanu", "EBC"),
    ("Dhanuk", "EBC"),
    ("Noniya", "EBC"),
    ("Surjapuri Muslim", "BC-II"),
    ("Pan / Sawasi / Panr", "SC"),
    ("Chandravanshi / Kahar", "EBC"),
    ("Nai", "EBC"),
    ("Barhai", "EBC"),
    ("Dhuniya (Muslim)", "EBC"),
    ("Prajapati / Kumhar", "EBC"),
    ("Raine / Kunjra", "EBC"),
    ("Pasi", "SC"),
    ("Bind", "EBC"),
    ("Kulhaiya", "BC-II"),
    ("Pathan / Khan", "GEN"),
    ("Dhobi / Rajak", "SC"),
    ("Kayastha", "GEN"),
    ("Kamar / Lohar / Karmakar", "EBC"),
    ("Haluai", "EBC"),
    ("Kewat", "EBC"),
    ("Gangota", "EBC"),
    ("Beldar", "EBC"),
    ("Goswami / Sanyasi / Gosain", "BC-II"),
)

PARTIES = (
    ("Bharatiya Janata Party (BJP)", "Narendra Modi"),
    ("Janata Dal (United) [JD(U)]", "Nitish Kumar"),
    ("Rashtriya Janata Dal (RJD)", "Lalu Prasad Yadav"),
    ("Indian National Congress (INC)", "Mallikarjun Kharge"),
    ("Lok Janshakti Party (Ram Vilas) [LJP (RV)]", "Chirag Paswan"),
    ("Hindustani Awam Morcha (Secular) [HAM(S)]", "Jitan Ram Manjhi"),
    ("Vikassheel Insaan Party (VIP)", "Mukesh Sahani"),
    ("Jan Suraaj Party (JSP)", "Prashant Kishor"),
    ("All India Majlis-e-Ittehadul Muslimeen (AIMIM)", "Asaduddin Owaisi"),
    ("Bahujan Samaj Party (BSP)", "Mayawati"),
    ("Communist Party of India (Marxist-Leninist) Liberation [CPI(ML)(L)]", "Dipankar Bhattacharya"),
    ("Communist Party of India (CPI)", "D. Raja"),
    ("Communist Party of India (Marxist) [CPI(M)]", "M. A. Baby"),
    ("Rashtriya Lok Morcha (RLM)", "Upendra Kushwaha"),
    ("Indian Inclusive Party (IIP)", "Indrajeet Prasad Gupta"),
)

CATEGORIES = ("GEN", "BC-II", "EBC", "SC")
OCCUPATIONS = (
    "Teacher",
    "Bank official",
    "Professor",
    "Police department",
    "House-wife",
    "Nurse",
    "Aanganwadi",
    "Peon",
    "Farmer",
    "Shopkeeper",
    "Other",
)
FARMER_KINDS = ("Animal", "Crops", "Fish", "Poultry", "Other")
SHOP_KINDS = (
    "Cloth",
    "Medical",
    "Furniture",
    "Kirana",
    "Printing press",
    "Photography and cyber cafe",
    "Dairy",
    "Electronics",
    "Sweet shops",
    "Hotel",
    "Butcher",
    "Other",
)

# Same bytes as pipeline._id(publication, source_url, page_no, serial).
VOTER_KEY_SQL = (
    "to_hex(sha256(cast(concat("
    "v.publication, '|', ifnull(v.source_url, ''), '|', "
    "ifnull(cast(v.page_no as string), ''), '|', cast(v.serial as string)"
    ") as bytes)))"
)

SORTS = {
    "name": "v.name",
    "ward_no": "v.ward_no",
    "serial": "v.serial",
    "epic": "v.epic",
    "relation": "v.relation",
    "relation_name": "v.relation_name",
    "house_no": "v.house_no",
    "age": AGE_SQL,
    "gender": "v.gender",
    "part_no": "v.part_no",
    "religion": "m.religion",
    "caste": "m.caste",
    "category": "m.category",
    "occupation": "m.occupation",
    "farmer": "m.farmer_kinds",
    "shop": "m.shop_kinds",
    "farmer_other": "m.farmer_other",
    "shop_other": "m.shop_other",
    "occupation_other": "m.occupation_other",
    "ideology": "m.ideology",
    "leader": "m.leader",
}

_TEXT_FILTERS = {
    "name": ("v.name", "hindi"),
    "epic": ("v.epic", "text"),
    "relation": ("v.relation", "hindi"),
    "relation_name": ("v.relation_name", "hindi"),
    "house_no": ("v.house_no", "hindi"),
    "gender": ("v.gender", "hindi"),
    "serial": ("v.serial", "number"),
    "part_no": ("v.part_no", "number"),
    "farmer_other": ("m.farmer_other", "hindi"),
    "shop_other": ("m.shop_other", "hindi"),
    "occupation_other": ("m.occupation_other", "hindi"),
}

FILTER_KEYS = (
    *tuple(_TEXT_FILTERS),
    "religion",
    "caste",
    "category",
    "occupation",
    "farmer",
    "shop",
    "ideology",
    "leader",
    "age",
)

_CASTE_CATEGORY = dict(CASTES)
_PARTY_LEADER = dict(PARTIES)


def fields_payload() -> dict:
    return {
        "religions": list(RELIGIONS),
        "castes": [{"name": name, "category": category} for name, category in CASTES],
        "categories": list(CATEGORIES),
        "occupations": list(OCCUPATIONS),
        "farmer_kinds": list(FARMER_KINDS),
        "shop_kinds": list(SHOP_KINDS),
        "ideologies": [{"name": name, "leader": leader} for name, leader in PARTIES],
        "leaders": [leader for _, leader in PARTIES],
        "age_bands": age_labels(),
    }


def clean_mark(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AppError("Voter mark is invalid")
    voter_key = str(payload.get("voter_key") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", voter_key):
        raise AppError("Unknown voter")
    religion = str(payload.get("religion") or "").strip()
    caste = str(payload.get("caste") or "").strip()
    occupation = str(payload.get("occupation") or "").strip()
    ideology = str(payload.get("ideology") or "").strip()
    if religion and religion not in RELIGIONS:
        raise AppError("Unknown religion")
    if caste and caste not in _CASTE_CATEGORY:
        raise AppError("Unknown caste")
    if occupation and occupation not in OCCUPATIONS:
        raise AppError("Unknown occupation")
    if ideology and ideology not in _PARTY_LEADER:
        raise AppError("Unknown ideology")
    farmer = _chosen(payload.get("farmer_kinds"), FARMER_KINDS) if occupation == "Farmer" else []
    shop = _chosen(payload.get("shop_kinds"), SHOP_KINDS) if occupation == "Shopkeeper" else []
    return {
        "voter_key": voter_key,
        "religion": religion,
        "caste": caste,
        "category": _CASTE_CATEGORY.get(caste, ""),
        "occupation": occupation,
        "farmer_kinds": _pack(farmer),
        "farmer_other": _note(payload.get("farmer_other")) if "Other" in farmer else "",
        "shop_kinds": _pack(shop),
        "shop_other": _note(payload.get("shop_other")) if "Other" in shop else "",
        "occupation_other": _note(payload.get("occupation_other")) if occupation == "Other" else "",
        "ideology": ideology,
        "leader": _PARTY_LEADER.get(ideology, ""),
    }


def mark_public(mark: dict) -> dict:
    return {
        "voter_key": mark["voter_key"],
        "religion": mark["religion"] or None,
        "caste": mark["caste"] or None,
        "category": mark["category"] or None,
        "occupation": mark["occupation"] or None,
        "farmer_kinds": unpack(mark["farmer_kinds"]),
        "farmer_other": mark["farmer_other"],
        "shop_kinds": unpack(mark["shop_kinds"]),
        "shop_other": mark["shop_other"],
        "occupation_other": mark["occupation_other"],
        "ideology": mark["ideology"] or None,
        "leader": mark["leader"] or None,
    }


def present_voter(row: dict) -> dict:
    mark = mark_public(
        {
            "voter_key": row.get("voter_key") or "",
            "religion": row.get("religion") or "",
            "caste": row.get("caste") or "",
            "category": row.get("category") or "",
            "occupation": row.get("occupation") or "",
            "farmer_kinds": row.get("farmer_kinds") or "",
            "farmer_other": row.get("farmer_other") or "",
            "shop_kinds": row.get("shop_kinds") or "",
            "shop_other": row.get("shop_other") or "",
            "occupation_other": row.get("occupation_other") or "",
            "ideology": row.get("ideology") or "",
            "leader": row.get("leader") or "",
        }
    )
    return {
        "serial": row.get("serial"),
        "epic": row.get("epic"),
        "name": row.get("name"),
        "relation": row.get("relation"),
        "relation_name": row.get("relation_name"),
        "house_no": row.get("house_no"),
        "age": row.get("age"),
        "gender": row.get("gender"),
        "assembly_ref": row.get("assembly_ref"),
        "part_no": row.get("part_no"),
        "ward_no": row.get("ward_no"),
        **mark,
    }


def extra_where(filters: dict) -> tuple[str, list[dict]]:
    clauses: list[str] = []
    params: list[dict] = []
    for key, allowed, column in (
        ("religion", RELIGIONS, "m.religion"),
        ("caste", tuple(_CASTE_CATEGORY), "m.caste"),
        ("category", CATEGORIES, "m.category"),
        ("occupation", OCCUPATIONS, "m.occupation"),
        ("ideology", tuple(_PARTY_LEADER), "m.ideology"),
        ("leader", tuple(leader for _, leader in PARTIES), "m.leader"),
    ):
        value = str(filters.get(key) or "").strip()
        if not value:
            continue
        if value not in allowed:
            raise AppError(f"Unknown {key}")
        clauses.append(f"{column} = @{key}")
        params.append(string_param(key, value))
    _kind_filter(filters, "farmer", FARMER_KINDS, "m.farmer_kinds", "farmer_kind", clauses, params)
    _kind_filter(filters, "shop", SHOP_KINDS, "m.shop_kinds", "shop_kind", clauses, params)
    age = str(filters.get("age") or "").strip()
    if age:
        clause, extra = age_where(age)
        clauses.append(clause)
        params.extend(extra)
    index = 0
    for key, (column, kind) in _TEXT_FILTERS.items():
        clause, extra = column_search(column, str(filters.get(key) or ""), f"c{index}", kind)
        if not clause:
            continue
        clauses.append(clause if clause.startswith("(") else f"({clause})")
        params.extend(extra)
        index += 1
    return " and ".join(clauses), params


def order_clause(sort: str, direction: str) -> str:
    if not sort:
        return "v.ward_no, v.part_no, v.serial"
    column = SORTS.get(sort)
    if column is None:
        raise AppError("Unknown sort")
    if direction not in {"asc", "desc"}:
        raise AppError("Unknown sort direction")
    return f"{column} {direction} nulls last, v.serial"


def unpack(value: object) -> list[str]:
    return [part for part in str(value or "").split("|") if part]


def _chosen(raw: object, allowed: tuple[str, ...]) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise AppError("Occupation details are invalid")
    picked = {str(item).strip() for item in raw if str(item).strip()}
    unknown = picked - set(allowed)
    if unknown:
        raise AppError("Unknown occupation detail")
    return [item for item in allowed if item in picked]


def _pack(items: list[str]) -> str:
    if not items:
        return ""
    return "|" + "|".join(items) + "|"


def _note(value: object) -> str:
    return str(value or "").strip()[:120]


def _kind_filter(
    filters: dict,
    key: str,
    allowed: tuple[str, ...],
    column: str,
    param: str,
    clauses: list[str],
    params: list[dict],
) -> None:
    value = str(filters.get(key) or "").strip()
    if not value:
        return
    if value not in allowed:
        raise AppError(f"Unknown {key}")
    clauses.append(f"ifnull({column}, '') like @{param}")
    params.append(string_param(param, f"%|{value}|%"))
