from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone

import httpx

from adapters.job_store import JobStore
from adapters.object_store import ObjectStore, sha256
from adapters.page_reader import PageReader, page_count, render_page
from adapters.qstash import QStash, lane_for
from adapters.redis_client import RedisClient
from adapters.roll_store import RollStore
from domain.models import AppError, Body, VoterCard
from services.catalog import Catalog

log = logging.getLogger(__name__)
_MAX_PAGES = 80


class Pipeline:
    def __init__(
        self,
        catalog: Catalog,
        jobs: JobStore,
        queue: QStash,
        redis: RedisClient,
        store: ObjectStore,
        reader: PageReader,
        rolls: RollStore,
    ) -> None:
        self.catalog = catalog
        self.jobs = jobs
        self.queue = queue
        self.redis = redis
        self.store = store
        self.reader = reader
        self.rolls = rolls

    def discover(self, message: dict) -> None:
        job = self._job(message["job_id"])
        if job["status"] == "ready":
            return
        lock = f"discover:{job['id']}"
        if not self.redis.lock(lock, 180):
            return
        try:
            body = Body(
                publication=job["publication"],
                district_id=job["district_id"],
                district_name=job["district_name"],
                prakhand_id=job["prakhand_id"],
                prakhand_name=job["prakhand_name"],
                body_type=job["body_type"],
                body_id=job["body_id"],
                body_name=job["body_name"],
                match_name=_match_name(job),
            )
            links = self.catalog.links(body)
            self.jobs.set_expected(job["id"], [link.source_url for link in links])
            for link in links:
                file_id, status = self.jobs.upsert_file(str(uuid.uuid4()), job["id"], link.source_url, link.ward_no)
                if status != "ready":
                    self._publish(message["callback_base"], "/internal/qstash/file", {"job_id": job["id"], "file_id": file_id})
            self._settle(job["id"])
        finally:
            self.redis.unlock(lock)

    def store_file(self, message: dict) -> None:
        item = self.jobs.get_file(message["file_id"])
        if item is None:
            raise AppError("Unknown roll file", 404)
        if item["status"] == "ready":
            return
        lock = f"file:{item['id']}"
        if not self.redis.lock(lock, 300):
            raise AppError("File is already being saved", 503)
        try:
            current = self.jobs.get_file(item["id"])
            if current is None or current["status"] == "ready":
                return
            if not current["s3_uri"]:
                pdf = _download(current["source_url"])
                count = page_count(pdf)
                if count < 1 or count > _MAX_PAGES:
                    raise AppError(f"PDF has {count} pages", 400)
                job = self._job(current["job_id"])
                key = _object_key(job, current["ward_no"], sha256(pdf))
                uri = self.store.put_pdf(key, pdf)
                self.jobs.mark_stored(current["id"], uri, sha256(pdf), count)
            stored = self.jobs.get_file(current["id"])
            if stored is None or not stored["page_count"]:
                raise AppError("Stored PDF has no pages", 500)
            for page_no in range(1, int(stored["page_count"]) + 1):
                if self.jobs.page_status(stored["id"], page_no) == "ready":
                    continue
                self._publish(
                    message["callback_base"],
                    "/internal/qstash/page",
                    {"job_id": stored["job_id"], "file_id": stored["id"], "page_no": page_no},
                )
        except AppError as exc:
            self.jobs.mark_file_error(item["id"], exc.message)
            raise
        finally:
            self.redis.unlock(lock)

    def read_page(self, message: dict) -> None:
        file_id = message["file_id"]
        page_no = int(message["page_no"])
        if self.jobs.page_status(file_id, page_no) == "ready":
            self._settle(message["job_id"])
            return
        lock = f"page:{file_id}:{page_no}"
        if not self.redis.lock(lock, 240):
            raise AppError("Page is already being read", 503)
        try:
            if self.jobs.page_status(file_id, page_no) == "ready":
                return
            item = self.jobs.get_file(file_id)
            if item is None or not item["s3_uri"]:
                raise AppError("PDF is not in storage yet", 503)
            job = self._job(item["job_id"])
            pdf = self.store.get_bytes(item["s3_uri"])
            image = render_page(pdf, page_no)
            reading = self.reader.read_page(image, item["ward_no"])
            ward_no = reading["ward_no"] or item["ward_no"]
            part_no = reading["part_no"] or 1
            now = datetime.now(timezone.utc).isoformat()
            if reading["page_kind"] == "cover" and reading["total_count"]:
                self.rolls.insert_ward(
                    {
                        "_insert_id": _id(job["publication"], item["source_url"], page_no, "cover"),
                        "publication": job["publication"],
                        "district": job["district_name"],
                        "prakhand": job["prakhand_name"],
                        "body_type": job["body_type"],
                        "body_name": job["body_name"],
                        "ward_no": ward_no,
                        "part_no": part_no,
                        "male_count": reading["male_count"],
                        "female_count": reading["female_count"],
                        "total_count": reading["total_count"],
                        "source_url": item["source_url"],
                        "ingested_at": now,
                    }
                )
            self.rolls.insert_voters(
                [
                    _voter_row(job, item["source_url"], page_no, ward_no, part_no, card, now)
                    for card in reading["voters"]
                ]
            )
            self.jobs.mark_page(file_id, page_no, "ready", len(reading["voters"]))
            self._finish_file(file_id)
            self._settle(job["id"])
        except Exception as exc:
            detail = exc.message if isinstance(exc, AppError) else str(exc)
            if not _retryable(detail):
                self.jobs.mark_page(file_id, page_no, "failed", 0, detail[:500])
                self._finish_file(file_id)
                self._settle(str(message["job_id"]))
            raise
        finally:
            self.redis.unlock(lock)

    def _finish_file(self, file_id: str) -> None:
        outcome = self.jobs.file_outcome(file_id)
        if outcome == "ready":
            self.jobs.mark_file_ready(file_id)
        elif outcome == "failed":
            self.jobs.mark_file_error(file_id, "One or more pages could not be read")

    def _settle(self, job_id: str) -> None:
        progress = self.jobs.job_progress(job_id)
        if not progress:
            return
        files = progress["files"]
        expected = json.loads(progress["job"]["expected_urls"] or "[]")
        if progress["complete"] and progress["voter_count"] > 0:
            self.jobs.mark_downloaded(progress["job"]["body_key"], job_id)
            return
        finished = bool(expected) and len(files) == len(expected) and all(
            item["status"] in {"ready", "failed"} for item in files
        )
        if finished:
            message = "No voter cards were read" if progress["voter_count"] < 1 else "Some ward PDFs could not be read"
            self.jobs.set_status(job_id, "failed", message)
            return
        if files:
            self.jobs.set_status(job_id, "reading")

    def _publish(self, base: str, path: str, payload: dict) -> None:
        payload = {**payload, "callback_base": base.rstrip("/")}
        self.queue.publish(f"{base.rstrip('/')}{path}", payload, lane=lane_for(path))

    def _job(self, job_id: str) -> dict:
        job = self.jobs.get_job(job_id)
        if job is None:
            raise AppError("Unknown ingest job", 404)
        return job


def _voter_row(job: dict, source_url: str, page_no: int, ward_no: int | None, part_no: int, card: VoterCard, now: str) -> dict:
    return {
        "_insert_id": _id(job["publication"], source_url, page_no, card.serial),
        "publication": job["publication"],
        "district": job["district_name"],
        "prakhand": job["prakhand_name"],
        "body_type": job["body_type"],
        "body_name": job["body_name"],
        "ward_no": ward_no,
        "part_no": part_no,
        "serial": card.serial,
        "epic": card.epic,
        "name": card.name,
        "relation": card.relation,
        "relation_name": card.relation_name,
        "house_no": card.house_no,
        "age": card.age,
        "gender": card.gender,
        "assembly_ref": card.assembly_ref,
        "source_url": source_url,
        "page_no": page_no,
        "ingested_at": now,
    }


def _object_key(job: dict, ward_no: int | None, digest: str) -> str:
    ward = f"ward-{int(ward_no):02d}" if ward_no else "ward-unknown"
    return (
        f"rolls/{_slug(job['publication'])}/{_slug(job['district_id'])}/"
        f"{_slug(job['body_type'])}/{_slug(job['body_id'])}/{ward}/{digest[:16]}.pdf"
    )


def _download(url: str) -> bytes:
    try:
        response = httpx.get(url, timeout=90, follow_redirects=True, headers={"User-Agent": "PsAnaRollIngest/1.0"})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AppError(f"PDF download failed: {exc}", 502) from exc
    if not response.content.startswith(b"%PDF"):
        raise AppError("Downloaded file is not a PDF", 502)
    return response.content


def _match_name(job: dict) -> str:
    if job["body_type"] != "nagar_panchayat":
        return job["body_name"]
    from config.sources import NAGAR_ROLLS

    for source in NAGAR_ROLLS:
        if source["publication"] != job["publication"]:
            continue
        for body in source["bodies"]:
            if str(body["id"]) == job["body_id"]:
                return body["name"]
    return job["body_name"]


def _retryable(detail: str) -> bool:
    text = detail.lower()
    return any(token in text for token in ("429", "resource exhausted", "503", "timeout", "timed out"))


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-") or "item"


def _id(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode()).hexdigest()
