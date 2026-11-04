from __future__ import annotations

import json
import ssl
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote, urlparse

import pg8000.native

from config.schema import STATEMENTS

_ready = False


def _connect(db_url: str) -> pg8000.native.Connection:
    parsed = urlparse(db_url)
    return pg8000.native.Connection(
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        host=parsed.hostname or "",
        port=parsed.port or 5432,
        database=(parsed.path or "/postgres").lstrip("/"),
        ssl_context=_ssl_context(),
        timeout=30,
    )


def _ssl_context() -> ssl.SSLContext:
    # The session pooler chain is signed by Supabase's own CA.
    ca_file = Path(__file__).with_name("supabase-ca.crt")
    return ssl.create_default_context(cafile=str(ca_file))


@contextmanager
def connection(db_url: str) -> Iterator[pg8000.native.Connection]:
    global _ready
    conn = _connect(db_url)
    try:
        if not _ready:
            for statement in STATEMENTS:
                conn.run(statement)
            _ready = True
        yield conn
    finally:
        conn.close()


class JobStore:
    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    def downloaded_job(self, body_key: str) -> str | None:
        with connection(self.db_url) as conn:
            rows = conn.run(
                "select job_id from public.downloaded_bodies where body_key = :body_key",
                body_key=body_key,
            )
        return str(rows[0][0]) if rows else None

    def open_job(self, body_key: str) -> str | None:
        with connection(self.db_url) as conn:
            rows = conn.run(
                """
                select id from public.ingest_jobs
                where body_key = :body_key and status not in ('ready', 'failed')
                order by created_at desc
                limit 1
                """,
                body_key=body_key,
            )
        return str(rows[0][0]) if rows else None

    def create_job(self, job: dict) -> None:
        with connection(self.db_url) as conn:
            conn.run(
                """
                insert into public.ingest_jobs (
                  id, user_id, publication, district_id, district_name, prakhand_id,
                  prakhand_name, body_type, body_id, body_name, body_key, status
                ) values (
                  :id, :user_id, :publication, :district_id, :district_name, :prakhand_id,
                  :prakhand_name, :body_type, :body_id, :body_name, :body_key, 'queued'
                )
                """,
                **job,
            )

    def get_job(self, job_id: str) -> dict | None:
        with connection(self.db_url) as conn:
            rows = conn.run(
                """
                select id, user_id, publication, district_id, district_name, prakhand_id,
                       prakhand_name, body_type, body_id, body_name, body_key, status,
                       error, expected_urls
                from public.ingest_jobs where id = :id
                """,
                id=job_id,
            )
        if not rows:
            return None
        columns = [
            "id", "user_id", "publication", "district_id", "district_name", "prakhand_id",
            "prakhand_name", "body_type", "body_id", "body_name", "body_key", "status",
            "error", "expected_urls",
        ]
        job = dict(zip(columns, rows[0], strict=True))
        for key in ("id", "user_id"):
            job[key] = str(job[key])
        return job

    def set_status(self, job_id: str, status: str, error: str | None = None) -> None:
        with connection(self.db_url) as conn:
            conn.run(
                "update public.ingest_jobs set status = :status, error = :error where id = :id",
                id=job_id,
                status=status,
                error=error,
            )

    def set_expected(self, job_id: str, urls: list[str]) -> None:
        with connection(self.db_url) as conn:
            conn.run(
                """
                update public.ingest_jobs
                set expected_urls = :urls, status = 'downloading'
                where id = :id
                """,
                id=job_id,
                urls=json.dumps(urls),
            )

    def upsert_file(self, file_id: str, job_id: str, url: str, ward_no: int | None) -> tuple[str, str]:
        with connection(self.db_url) as conn:
            rows = conn.run(
                """
                insert into public.source_files (id, job_id, source_url, ward_no, status)
                values (:id, :job_id, :source_url, :ward_no, 'queued')
                on conflict (source_url) do update set
                  ward_no = excluded.ward_no,
                  job_id = case
                    when public.source_files.status = 'ready' then public.source_files.job_id
                    else excluded.job_id
                  end,
                  status = case
                    when public.source_files.status = 'ready' then public.source_files.status
                    else 'queued'
                  end,
                  error = case
                    when public.source_files.status = 'ready' then public.source_files.error
                    else null
                  end
                returning id, status
                """,
                id=file_id,
                job_id=job_id,
                source_url=url,
                ward_no=ward_no,
            )
        return str(rows[0][0]), str(rows[0][1])

    def get_file(self, file_id: str) -> dict | None:
        with connection(self.db_url) as conn:
            rows = conn.run(
                """
                select id, job_id, source_url, ward_no, content_hash, s3_uri, page_count, status, error
                from public.source_files where id = :id
                """,
                id=file_id,
            )
        if not rows:
            return None
        columns = ["id", "job_id", "source_url", "ward_no", "content_hash", "s3_uri", "page_count", "status", "error"]
        item = dict(zip(columns, rows[0], strict=True))
        item["id"] = str(item["id"])
        item["job_id"] = str(item["job_id"])
        return item

    def mark_stored(self, file_id: str, s3_uri: str, content_hash: str, page_count: int) -> None:
        with connection(self.db_url) as conn:
            conn.run(
                """
                update public.source_files
                set s3_uri = :s3_uri, content_hash = :content_hash, page_count = :page_count, status = 'stored', error = null
                where id = :id
                """,
                id=file_id,
                s3_uri=s3_uri,
                content_hash=content_hash,
                page_count=page_count,
            )
            for page_no in range(1, page_count + 1):
                conn.run(
                    """
                    insert into public.source_pages (file_id, page_no, status)
                    values (:file_id, :page_no, 'queued')
                    on conflict (file_id, page_no) do nothing
                    """,
                    file_id=file_id,
                    page_no=page_no,
                )

    def page_status(self, file_id: str, page_no: int) -> str | None:
        with connection(self.db_url) as conn:
            rows = conn.run(
                "select status from public.source_pages where file_id = :file_id and page_no = :page_no",
                file_id=file_id,
                page_no=page_no,
            )
        return str(rows[0][0]) if rows else None

    def mark_page(self, file_id: str, page_no: int, status: str, voter_count: int, error: str | None = None) -> None:
        with connection(self.db_url) as conn:
            conn.run(
                """
                update public.source_pages
                set status = :status, voter_count = :voter_count, error = :error
                where file_id = :file_id and page_no = :page_no
                """,
                file_id=file_id,
                page_no=page_no,
                status=status,
                voter_count=voter_count,
                error=error,
            )

    def file_outcome(self, file_id: str) -> str | None:
        with connection(self.db_url) as conn:
            rows = conn.run(
                """
                select f.page_count,
                       count(*) filter (where p.status = 'ready'),
                       count(*) filter (where p.status = 'failed')
                from public.source_files f
                left join public.source_pages p on p.file_id = f.id
                where f.id = :id
                group by f.page_count
                """,
                id=file_id,
            )
        if not rows or rows[0][0] is None:
            return None
        total, ready, failed = (int(rows[0][0]), int(rows[0][1]), int(rows[0][2]))
        if total < 1:
            return None
        if ready == total:
            return "ready"
        if ready + failed == total:
            return "failed"
        return None

    def file_is_complete(self, file_id: str) -> bool:
        with connection(self.db_url) as conn:
            rows = conn.run(
                """
                select page_count,
                       count(*) filter (where p.status = 'ready'),
                       count(p.page_no)
                from public.source_files f
                left join public.source_pages p on p.file_id = f.id
                where f.id = :id
                group by f.page_count
                """,
                id=file_id,
            )
        if not rows or rows[0][0] is None:
            return False
        return int(rows[0][0]) > 0 and int(rows[0][1]) == int(rows[0][0])

    def mark_file_ready(self, file_id: str) -> None:
        with connection(self.db_url) as conn:
            conn.run(
                "update public.source_files set status = 'ready', error = null where id = :id",
                id=file_id,
            )

    def mark_file_error(self, file_id: str, error: str) -> None:
        with connection(self.db_url) as conn:
            conn.run(
                "update public.source_files set status = 'failed', error = :error where id = :id",
                id=file_id,
                error=error[:500],
            )

    def job_progress(self, job_id: str) -> dict:
        job = self.get_job(job_id)
        if job is None:
            return {}
        urls = json.loads(job["expected_urls"] or "[]")
        files: list[dict] = []
        if urls:
            with connection(self.db_url) as conn:
                for url in urls:
                    rows = conn.run(
                        """
                        select f.id, f.ward_no, f.status, f.page_count, f.error, f.source_url,
                               count(p.page_no) filter (where p.status = 'ready'),
                               coalesce(sum(p.voter_count), 0)
                        from public.source_files f
                        left join public.source_pages p on p.file_id = f.id
                        where f.source_url = :source_url
                        group by f.id
                        """,
                        source_url=url,
                    )
                    if not rows:
                        continue
                    files.append(
                        {
                            "id": str(rows[0][0]),
                            "ward_no": rows[0][1],
                            "status": rows[0][2],
                            "page_count": rows[0][3] or 0,
                            "error": rows[0][4],
                            "source_url": rows[0][5],
                            "pages_ready": int(rows[0][6]),
                            "voter_count": int(rows[0][7]),
                        }
                    )
        voters = sum(item["voter_count"] for item in files)
        complete = bool(urls) and len(files) == len(urls) and all(item["status"] == "ready" for item in files)
        return {"job": job, "files": files, "voter_count": voters, "complete": complete}

    def mark_downloaded(self, body_key: str, job_id: str) -> None:
        with connection(self.db_url) as conn:
            conn.run(
                """
                insert into public.downloaded_bodies (body_key, job_id)
                values (:body_key, :job_id)
                on conflict (body_key) do nothing
                """,
                body_key=body_key,
                job_id=job_id,
            )
            conn.run(
                "update public.ingest_jobs set status = 'ready', error = null where id = :id",
                id=job_id,
            )

    def list_jobs(self, limit: int = 15, offset: int = 0, query: str = "", status: str = "") -> dict:
        limit = min(max(int(limit), 1), 40)
        offset = max(int(offset), 0)
        where: list[str] = []
        args: dict = {}
        text = query.strip()[:80]
        if text:
            where.append("(body_name ilike :q or district_name ilike :q or prakhand_name ilike :q)")
            args["q"] = f"%{text}%"
        if status == "reading":
            where.append("status in ('reading', 'queued')")
        elif status in {"ready", "failed"}:
            where.append("status = :status")
            args["status"] = status
        clause = " and ".join(where) if where else "true"
        with connection(self.db_url) as conn:
            grouped = conn.run(
                """
                select status, count(*)
                from public.ingest_jobs
                group by status
                """
            )
            total_rows = conn.run(f"select count(*) from public.ingest_jobs where {clause}", **args)
            rows = conn.run(
                f"""
                select id, body_name, body_type, body_id, district_id, district_name,
                       prakhand_id, prakhand_name, status, created_at
                from public.ingest_jobs
                where {clause}
                order by created_at desc
                limit :limit offset :offset
                """,
                **args,
                limit=limit,
                offset=offset,
            )
        by_status = {str(row[0]): int(row[1]) for row in grouped}
        return {
            "total": int(total_rows[0][0]) if total_rows else 0,
            "counts": {
                "all": sum(by_status.values()),
                "reading": by_status.get("reading", 0) + by_status.get("queued", 0),
                "ready": by_status.get("ready", 0),
                "failed": by_status.get("failed", 0),
            },
            "jobs": [
                {
                    "id": str(row[0]),
                    "body_name": row[1],
                    "body_type": row[2],
                    "body_id": row[3],
                    "district_id": row[4],
                    "district_name": row[5],
                    "prakhand_id": row[6],
                    "prakhand_name": row[7],
                    "status": row[8],
                    "created_at": row[9].isoformat(),
                }
                for row in rows
            ],
        }
