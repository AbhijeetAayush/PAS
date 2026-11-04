"""Age on the roll is the age printed in 2021.

The list shows that age plus the years since 2021. BigQuery uses the date in
India, so the number moves forward on 1 January without a new deploy.
"""

from __future__ import annotations

from adapters.roll_store import int_param
from domain.models import AppError

ROLL_YEAR = 2021

AGE_SQL = (
    "safe_cast(v.age as int64) + "
    f"(extract(year from current_date('Asia/Kolkata')) - {ROLL_YEAR})"
)


def current_age(printed: int, year: int) -> int:
    return printed + (year - ROLL_YEAR)


def age_bands() -> list[tuple[str, int, int | None]]:
    """18–25, then every five years. The last band is open."""
    bands: list[tuple[str, int, int | None]] = [("18-25", 18, 25)]
    start = 25
    while start < 95:
        end = start + 5
        bands.append((f"{start}-{end}", start, end))
        start = end
    bands.append(("95+", 95, None))
    return bands


def age_labels() -> list[str]:
    return [label for label, _, _ in age_bands()]


def age_where(value: str) -> tuple[str, list[dict]]:
    label = value.strip()
    match = next((band for band in age_bands() if band[0] == label), None)
    if match is None:
        raise AppError("Unknown age")
    _, low, high = match
    if high is None:
        return f"{AGE_SQL} >= @age_low", [int_param("age_low", low)]
    return f"{AGE_SQL} between @age_low and @age_high", [int_param("age_low", low), int_param("age_high", high)]
