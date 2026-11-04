from __future__ import annotations

import logging
from functools import cached_property, lru_cache

from adapters.job_store import JobStore
from adapters.object_store import ObjectStore
from adapters.page_reader import PageReader
from adapters.secret_store import SecretStore
from adapters.qstash import QStash
from adapters.redis_client import RedisClient
from adapters.roll_store import GoogleAuth, RollStore
from adapters.sec_client import SecClient
from config.settings import Settings, get_settings
from services.catalog import Catalog
from services.ingest import IngestService
from services.pipeline import Pipeline

log = logging.getLogger(__name__)


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.sec = SecClient()
        self.redis = (
            RedisClient(settings.upstash_redis_rest_url, settings.upstash_redis_rest_token)
            if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token
            else None
        )
        self.catalog = Catalog(self.sec, self.redis)

    def require_redis(self) -> RedisClient:
        self.settings.require("upstash_redis_rest_url", "upstash_redis_rest_token")
        if self.redis is None:
            raise RuntimeError("Redis is not configured")
        return self.redis

    @cached_property
    def jobs(self) -> JobStore:
        self.settings.require("supabase_db_url")
        return JobStore(self.settings.supabase_db_url)

    @cached_property
    def queue(self) -> QStash:
        self.settings.require("qstash_token", "qstash_current_signing_key", "qstash_next_signing_key")
        return QStash(
            self.settings.qstash_token,
            self.settings.qstash_current_signing_key,
            self.settings.qstash_next_signing_key,
            self.settings.qstash_url,
        )

    @cached_property
    def objects(self) -> ObjectStore:
        self.settings.require("pdf_bucket")
        return ObjectStore(self.settings.pdf_bucket)

    @cached_property
    def google(self) -> GoogleAuth:
        return GoogleAuth(self._service_account_b64())

    def _service_account_b64(self) -> str:
        inline = self.settings.gcp_service_account_json_b64.strip()
        if inline:
            return inline
        self.settings.require("gcp_service_account_secret")
        return SecretStore().get(self.settings.gcp_service_account_secret).strip()

    @cached_property
    def reader(self) -> PageReader:
        self.settings.require("gcp_project_id")
        return PageReader(
            self.google,
            self.settings.vertex_model,
            self.settings.gcp_project_id,
            self.settings.vertex_location,
        )

    @cached_property
    def rolls(self) -> RollStore:
        self.settings.require("gcp_project_id")
        return RollStore(
            self.google,
            self.settings.gcp_project_id,
            self.settings.bigquery_dataset,
            self.settings.bigquery_location,
        )

    @cached_property
    def pipeline(self) -> Pipeline:
        return Pipeline(
            self.catalog,
            self.jobs,
            self.queue,
            self.require_redis(),
            self.objects,
            self.reader,
            self.rolls,
        )

    @cached_property
    def ingest(self) -> IngestService:
        self.settings.require("worker_base_url")
        return IngestService(self.catalog, self.jobs, self.queue, self.settings.worker_base_url)


@lru_cache
def get_container() -> Container:
    return Container(get_settings())
