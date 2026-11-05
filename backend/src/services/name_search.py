"""Match Roman typing to Hindi text already stored on the roll.

The map is a fixed letter table. A search does not call a model. ABHI becomes
अभि, so अभिजीत and अभिषेक both match. Each medial "a" is tried as the short
vowel and as आ, and श/ष, त/ट, द/ड, न/ण are tried the same way, capped so one
lookup stays a handful of LIKE patterns. Those spellings are tried on every
Hindi column, not only the voter name.
"""

from __future__ import annotations

import re

from adapters.roll_store import string_param
from services.age import AGE_SQL

_VIRAMA = "्"
_MAX_FORMS = 16

# Whole words whose English spelling does not follow the letter map.
_FIXED = {
    "singh": ["सिंह"],
    "shri": ["श्री"],
    "sri": ["श्री"],
    "rishi": ["ऋषि"],
}

_VOWELS: list[tuple[str, list[str], list[str]]] = [
    ("aa", ["ा"], ["आ"]),
    ("ai", ["ै"], ["ऐ"]),
    ("au", ["ौ"], ["औ"]),
    ("ee", ["ी", "ि"], ["ई", "इ"]),
    ("ii", ["ी", "ि"], ["ई", "इ"]),
    ("oo", ["ू", "ु"], ["ऊ", "उ"]),
    ("uu", ["ू", "ु"], ["ऊ", "उ"]),
    ("a", ["", "ा"], ["अ", "आ"]),
    ("e", ["े"], ["ए"]),
    ("i", ["ि", "ी"], ["इ", "ई"]),
    ("o", ["ो"], ["ओ"]),
    ("u", ["ु", "ू"], ["उ", "ऊ"]),
]

# Longest spelling first. The first Devanagari letter is the usual one.
_CONSONANTS: list[tuple[str, list[str]]] = [
    ("ksh", ["क्ष"]),
    ("chh", ["छ"]),
    ("kh", ["ख"]),
    ("gh", ["घ"]),
    ("jh", ["झ"]),
    ("th", ["थ", "ठ"]),
    ("dh", ["ध", "ढ"]),
    ("ph", ["फ"]),
    ("bh", ["भ"]),
    ("ch", ["च"]),
    ("sh", ["श", "ष"]),
    ("k", ["क"]),
    ("g", ["ग"]),
    ("j", ["ज"]),
    ("t", ["त", "ट"]),
    ("d", ["द", "ड"]),
    ("n", ["न", "ण"]),
    ("p", ["प"]),
    ("b", ["ब"]),
    ("m", ["म"]),
    ("y", ["य"]),
    ("r", ["र"]),
    ("l", ["ल"]),
    ("w", ["व"]),
    ("v", ["व"]),
    ("f", ["फ"]),
    ("s", ["स"]),
    ("h", ["ह"]),
    ("q", ["क"]),
    ("x", ["क्ष"]),
    ("z", ["ज"]),
    ("c", ["क"]),
]

_STOPS = set("kgcjtdpb")


def spellings(word: str) -> list[str]:
    """Devanagari spellings to look for inside a Hindi name."""
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if len(cleaned) < 2:
        return []
    if cleaned in _FIXED:
        return list(_FIXED[cleaned])
    groups = _parse(cleaned)
    if not groups:
        return []
    forms = [form for form in _combine(groups) if len(form) >= 2]
    fixed = _FIXED.get(cleaned, [])
    return _uniq([*fixed, *forms])[:_MAX_FORMS]


# Roll columns that can hold Hindi, plus notes typed on a voter.
_HINDI_COLUMNS = (
    "v.name",
    "v.relation",
    "v.relation_name",
    "v.gender",
    "v.house_no",
    "v.assembly_ref",
    "m.farmer_other",
    "m.shop_other",
    "m.occupation_other",
)

_RAW_COLUMNS = (
    "v.name",
    "v.epic",
    "v.house_no",
    "v.relation",
    "v.relation_name",
    "v.gender",
    "v.assembly_ref",
    "m.religion",
    "m.caste",
    "m.category",
    "m.occupation",
    "m.farmer_kinds",
    "m.shop_kinds",
    "m.farmer_other",
    "m.shop_other",
    "m.occupation_other",
    "m.ideology",
    "m.leader",
)


def voter_search(needle: str) -> tuple[str, list[dict]]:
    """SQL boolean and BigQuery params. @q is the raw typed text.

    One concatenated LIKE per spelling, not one LIKE per column. The match is
    the same: the text can sit in any of those columns.
    """
    raw = f"%{needle.lower()}%"
    params: list[dict] = [string_param("q", raw)]
    branches = [
        f"{_haystack(_RAW_COLUMNS, lower=True)} like @q",
        "cast(v.serial as string) like @q",
        "cast(ifnull(v.part_no, 0) as string) like @q",
        "cast(ifnull(v.ward_no, 0) as string) like @q",
        f"cast({AGE_SQL} as string) like @q",
    ]
    groups = word_forms(needle)
    if groups:
        branches.append("(" + forms_clause(groups, _HINDI_COLUMNS, params) + ")")
    return " or ".join(branches), params


def column_search(column: str, needle: str, param: str, kind: str) -> tuple[str, list[dict]]:
    """One column filter. kind is hindi, text, or number."""
    cleaned = needle.strip().replace("%", "").replace("_", "")[:80]
    if not cleaned:
        return "", []
    params: list[dict] = [string_param(param, f"%{cleaned.lower()}%")]
    if kind == "number":
        base = f"cast({column} as string) like @{param}"
    else:
        base = f"lower(ifnull({column}, '')) like @{param}"
    if kind != "hindi":
        return base, params
    groups = word_forms(cleaned)
    if not groups:
        return base, params
    hindi = forms_clause(groups, (column,), params, prefix=f"{param}h")
    return f"({base} or ({hindi}))", params


def word_forms(needle: str) -> list[list[str]]:
    groups: list[list[str]] = []
    for word in re.split(r"\s+", needle.strip().lower()):
        if re.fullmatch(r"[a-z][a-z.'-]*", word):
            forms = spellings(word)
        elif re.search(r"[\u0900-\u097F]", word):
            forms = [word]
        else:
            continue
        if forms:
            groups.append(forms)
    return groups


def forms_clause(
    groups: list[list[str]],
    columns: tuple[str, ...],
    params: list[dict],
    prefix: str = "h",
) -> str:
    target = columns[0] if len(columns) == 1 else _haystack(columns, lower=False)
    parts: list[str] = []
    index = 0
    for forms in groups:
        choices: list[str] = []
        for form in forms:
            key = f"{prefix}{index}"
            params.append(string_param(key, f"%{form}%"))
            choices.append(f"{target} like @{key}")
            index += 1
        parts.append("(" + " or ".join(choices) + ")")
    return " and ".join(parts)


def _haystack(columns: tuple[str, ...], lower: bool) -> str:
    joined = ", ' ', ".join(f"ifnull({column}, '')" for column in columns)
    expr = f"concat({joined})"
    return f"lower({expr})" if lower else expr


def _parse(word: str) -> list[list[str]]:
    groups: list[list[str]] = []
    pending: list[list[str]] = []
    index = 0
    while index < len(word):
        if word.startswith("ngh", index) and pending:
            groups.append(_cluster(pending, None))
            pending = []
            groups.append(["ंह", "ंघ"])
            index += 3
            continue
        vowel = _vowel_at(word, index)
        if vowel is not None:
            length, matras, independents = vowel
            if pending:
                groups.append(_cluster(pending, matras))
                pending = []
            else:
                groups.append(independents)
            index += length
            continue
        if word[index] == "n" and _nasal_stop(word, index + 1):
            if pending:
                groups.append(_cluster(pending, None))
                pending = []
            groups.append(["ं"])
            index += 1
            continue
        consonant = _consonant_at(word, index)
        if consonant is None:
            index += 1
            continue
        length, letters = consonant
        pending.append(letters)
        index += length
    if pending:
        groups.append(_cluster(pending, None))
    return groups


def _cluster(consonants: list[list[str]], matras: list[str] | None) -> list[str]:
    marks = matras or [""]
    conjunct = _join(consonants, marks, virama=True)
    if len(consonants) == 1:
        return conjunct
    # "paswan" hides the vowel between स and व, while "prasad" really is the conjunct प्र.
    return _uniq([*conjunct, *_join(consonants, marks, virama=False)])


def _join(consonants: list[list[str]], marks: list[str], virama: bool) -> list[str]:
    prefixes = [""]
    for letters in consonants[:-1]:
        glue = _VIRAMA if virama else ""
        prefixes = [prefix + letter + glue for prefix in prefixes for letter in letters]
    return [prefix + letter + mark for prefix in prefixes for letter in consonants[-1] for mark in marks]


def _combine(groups: list[list[str]]) -> list[str]:
    primary = [group[0] for group in groups]
    found = ["".join(primary)]

    def add(pieces: list[str]) -> None:
        found.append("".join(pieces))

    for index, group in enumerate(groups):
        for alt in group[1:]:
            pieces = list(primary)
            pieces[index] = alt
            add(pieces)
    for left in range(len(groups)):
        for right in range(left + 1, len(groups)):
            for alt_left in groups[left][1:]:
                for alt_right in groups[right][1:]:
                    pieces = list(primary)
                    pieces[left] = alt_left
                    pieces[right] = alt_right
                    add(pieces)
                    if len(found) > 80:
                        return _uniq(found)
    return _uniq(found)


def _vowel_at(word: str, index: int) -> tuple[int, list[str], list[str]] | None:
    for spelling, matras, independents in _VOWELS:
        if word.startswith(spelling, index):
            return len(spelling), matras, independents
    return None


def _consonant_at(word: str, index: int) -> tuple[int, list[str]] | None:
    for spelling, letters in _CONSONANTS:
        if word.startswith(spelling, index):
            return len(spelling), letters
    return None


def _nasal_stop(word: str, index: int) -> bool:
    consonant = _consonant_at(word, index)
    if consonant is None or _vowel_at(word, index) is not None:
        return False
    spelling = next(item[0] for item in _CONSONANTS if word.startswith(item[0], index))
    return spelling[0] in _STOPS


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
