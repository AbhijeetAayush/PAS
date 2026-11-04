from __future__ import annotations

import json
import logging

import httpx

from adapters.redis_client import RedisClient
from adapters.sec_client import SecClient, parse_nagar_page
from config.sources import GRAM_PUBLICATION, NAGAR_ROLLS
from domain.models import AppError, Body, District, Prakhand, RollLink

log = logging.getLogger(__name__)


class Catalog:
    def __init__(self, sec: SecClient, redis: RedisClient | None = None) -> None:
        self.sec = sec
        self.redis = redis

    def districts(self) -> list[District]:
        rows = self._cached("sec:districts", 60 * 60 * 12, lambda: [
            {"id": item.id, "name": item.name} for item in self.sec.districts()
        ])
        return [District(item["id"], item["name"]) for item in rows]

    def prakhands(self, district_id: str) -> list[Prakhand]:
        rows = self._cached(
            f"sec:prakhand:{district_id}",
            60 * 60 * 12,
            lambda: [
                {"id": item.id, "name": item.name}
                for item in self.sec.prakhands(district_id)
            ],
        )
        return [Prakhand(item["id"], item["name"], district_id) for item in rows]

    def bodies(self, district_id: str, prakhand_id: str, body_type: str) -> list[Body]:
        if body_type == "nagar_panchayat":
            return [
                body
                for body in self._nagar_bodies()
                if body.district_id == district_id and body.prakhand_id == prakhand_id
            ]
        if body_type != "gram_panchayat":
            raise AppError("body_type must be gram_panchayat or nagar_panchayat")
        district = self._district(district_id)
        prakhand = self._prakhand(district_id, prakhand_id)
        return [
            Body(
                publication=GRAM_PUBLICATION,
                district_id=district_id,
                district_name=district.name,
                prakhand_id=prakhand_id,
                prakhand_name=prakhand.name,
                body_type="gram_panchayat",
                body_id=item["id"],
                body_name=item["name"],
                match_name=item["name"],
            )
            for item in self.sec.panchayats(district_id, prakhand_id)
        ]

    def get_body(self, district_id: str, prakhand_id: str, body_type: str, body_id: str) -> Body:
        for body in self.bodies(district_id, prakhand_id, body_type):
            if body.body_id == body_id:
                return body
        raise AppError("That panchayat is not in the selected block", 404)

    def links(self, body: Body) -> list[RollLink]:
        if body.body_type == "gram_panchayat":
            return self.sec.roll_links(body.district_id, body.prakhand_id, body.body_id)
        source = _nagar_source(body.district_id, body.publication)
        response = httpx.get(
            source["page_url"],
            timeout=40,
            follow_redirects=True,
            headers={"User-Agent": "PsAnaRollIngest/1.0"},
        )
        response.raise_for_status()
        found = parse_nagar_page(response.text, source["page_url"], body.match_name)
        if not found:
            raise AppError(f"No ward PDF on {source['page_url']} for {body.match_name}", 404)
        return found

    def _nagar_bodies(self) -> list[Body]:
        bodies: list[Body] = []
        for source in NAGAR_ROLLS:
            for item in source["bodies"]:
                bodies.append(
                    Body(
                        publication=source["publication"],
                        district_id=str(source["district_id"]),
                        district_name=source["district_name"],
                        prakhand_id=str(item["prakhand_id"]),
                        prakhand_name=item["prakhand_name"],
                        body_type="nagar_panchayat",
                        body_id=str(item["id"]),
                        body_name=item["name_hi"],
                        match_name=item["name"],
                    )
                )
        return bodies

    def _district(self, district_id: str) -> District:
        for district in self.districts():
            if district.id == district_id:
                return district
        raise AppError("Unknown district", 404)

    def _prakhand(self, district_id: str, prakhand_id: str) -> Prakhand:
        for prakhand in self.prakhands(district_id):
            if prakhand.id == prakhand_id:
                return prakhand
        raise AppError("Unknown prakhand", 404)

    def _cached(self, key: str, ttl: int, load):
        if self.redis is not None:
            try:
                hit = self.redis.get(key)
                if hit:
                    return json.loads(hit)
            except Exception:
                log.warning("Redis cache read failed", exc_info=True)
        value = load()
        if self.redis is not None:
            try:
                self.redis.set(key, json.dumps(value, ensure_ascii=False), ttl)
            except Exception:
                log.warning("Redis cache write failed", exc_info=True)
        return value


def _nagar_source(district_id: str, publication: str) -> dict:
    for source in NAGAR_ROLLS:
        if str(source["district_id"]) == district_id and source["publication"] == publication:
            return source
    raise AppError("No nagar roll page is configured for this district", 404)
