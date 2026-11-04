from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class District:
    id: str
    name: str


@dataclass(frozen=True)
class Prakhand:
    id: str
    name: str
    district_id: str


@dataclass(frozen=True)
class Body:
    publication: str
    district_id: str
    district_name: str
    prakhand_id: str
    prakhand_name: str
    body_type: str
    body_id: str
    body_name: str
    match_name: str = ""

    @property
    def key(self) -> str:
        return "|".join(
            [
                self.publication,
                self.district_id,
                self.prakhand_id,
                self.body_type,
                self.body_id,
            ]
        )


@dataclass(frozen=True)
class RollLink:
    source_url: str
    ward_no: int | None
    label: str


@dataclass(frozen=True)
class VoterCard:
    serial: int
    epic: str | None
    name: str
    relation: str
    relation_name: str
    house_no: str
    age: str
    gender: str
    assembly_ref: str | None


@dataclass(frozen=True)
class PageRead:
    page_kind: str
    ward_no: int | None
    part_no: int | None
    male_count: int | None
    female_count: int | None
    total_count: int | None
    voters: list[VoterCard]


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
