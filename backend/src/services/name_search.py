"""Match a Roman-typed name to Hindi text already stored on the roll.

The map is a fixed letter table. A search does not call a model. ABHI becomes
अभि, so अभिजीत and अभिषेक both match. Each medial "a" is tried as the short
vowel and as आ, and श/ष, त/ट, द/ड, न/ण are tried the same way, capped so one
lookup stays a handful of LIKE patterns.
"""

from __future__ import annotations

import re

from adapters.roll_store import string_param

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


def voter_search(needle: str) -> tuple[str, list[dict]]:
    """SQL boolean and BigQuery params. @q is the raw typed text."""
    raw = f"%{needle.lower()}%"
    params: list[dict] = [string_param("q", raw)]
    branches = [
        "lower(name) like @q",
        "lower(ifnull(epic, '')) like @q",
        "lower(ifnull(house_no, '')) like @q",
        "cast(serial as string) like @q",
    ]
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
    if groups:
        parts: list[str] = []
        index = 0
        for forms in groups:
            choices: list[str] = []
            for form in forms:
                key = f"h{index}"
                choices.append(f"name like @{key}")
                params.append(string_param(key, f"%{form}%"))
                index += 1
            parts.append("(" + " or ".join(choices) + ")")
        branches.append("(" + " and ".join(parts) + ")")
    return " or ".join(branches), params


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
