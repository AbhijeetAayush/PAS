from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from adapters.qstash import QStash, lane_for
from adapters.job_store import JobStore
from domain.models import AppError
from services.catalog import Catalog

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestStart:
    status: str
    job_id: str
    body_id: str = ""


class IngestService:
    def __init__(self, catalog: Catalog, jobs: JobStore, queue: QStash, worker_base_url: str) -> None:
        self.catalog = catalog
        self.jobs = jobs
        self.queue = queue
        self.worker_base_url = worker_base_url.rstrip("/")

    def start(self, user_id: str, district_id: str, prakhand_id: str, body_type: str, body_id: str) -> IngestStart:
        if not self.worker_base_url:
            raise AppError("Worker URL is not configured", 503)
        body = self.catalog.get_body(district_id, prakhand_id, body_type, body_id)
        done = self.jobs.downloaded_job(body.key)
        if done:
            return IngestStart("already_downloaded", done, body.body_id)
        existing = self.jobs.open_job(body.key)
        if existing:
            self._publish("/internal/qstash/discover", {"job_id": existing})
            return IngestStart("resume", existing, body.body_id)
        job_id = str(uuid.uuid4())
        self.jobs.create_job(
            {
                "id": job_id,
                "user_id": user_id,
                "publication": body.publication,
                "district_id": body.district_id,
                "district_name": body.district_name,
                "prakhand_id": body.prakhand_id,
                "prakhand_name": body.prakhand_name,
                "body_type": body.body_type,
                "body_id": body.body_id,
                "body_name": body.body_name,
                "body_key": body.key,
            }
        )
        self._publish("/internal/qstash/discover", {"job_id": job_id})
        log.info("queued ingest %s for %s", job_id, body.key)
        return IngestStart("queued", job_id, body.body_id)

    def start_many(
        self,
        user_id: str,
        district_id: str,
        prakhand_id: str,
        body_type: str,
        body_ids: list[str],
    ) -> list[IngestStart]:
        if not self.worker_base_url:
            raise AppError("Worker URL is not configured", 503)
        if not body_ids:
            raise AppError("body_id is required")
        if len(body_ids) > 100:
            raise AppError("Select at most 100 panchayats at a time")
        bodies = [
            self.catalog.get_body(district_id, prakhand_id, body_type, body_id)
            for body_id in body_ids
        ]
        return [
            self.start(user_id, district_id, prakhand_id, body_type, body.body_id)
            for body in bodies
        ]

    def _publish(self, path: str, payload: dict) -> None:
        payload = {**payload, "callback_base": self.worker_base_url}
        self.queue.publish(f"{self.worker_base_url}{path}", payload, lane=lane_for(path))
