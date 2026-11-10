from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Header, Request

from api.container import Container, get_container
from api.security import require_user
from domain.models import AppError
from services.age import AGE_SQL
from services.ingest import IngestStart
from services.name_search import voter_search
from services.voter_marks import (
    FILTER_KEYS,
    VOTER_KEY_SQL,
    clean_mark,
    extra_where,
    fields_payload,
    mark_public,
    order_clause,
    present_voter,
)

log = logging.getLogger(__name__)
router = APIRouter()


def container() -> Container:
    return get_container()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/config/public")
def public_config(app: Container = Depends(container)) -> dict:
    app.settings.require("supabase_url", "supabase_anon_key")
    return {
        "supabaseUrl": app.settings.supabase_url,
        "supabaseAnonKey": app.settings.supabase_anon_key,
    }


@router.get("/catalog/districts")
def districts(app: Container = Depends(container)) -> dict:
    rows = app.catalog.districts()
    return {"districts": [{"id": item.id, "name": item.name} for item in rows]}


@router.get("/catalog/prakhands")
def prakhands(district_id: str, app: Container = Depends(container)) -> dict:
    rows = app.catalog.prakhands(district_id)
    return {"prakhands": [{"id": item.id, "name": item.name} for item in rows]}


@router.get("/catalog/bodies")
def bodies(district_id: str, prakhand_id: str, body_type: str, app: Container = Depends(container)) -> dict:
    rows = app.catalog.bodies(district_id, prakhand_id, body_type)
    return {
        "bodies": [
            {
                "id": item.body_id,
                "name": item.body_name,
                "body_type": item.body_type,
                "publication": item.publication,
            }
            for item in rows
        ]
    }


@router.post("/ingest")
def start_ingest(payload: dict, authorization: str | None = Header(default=None), app: Container = Depends(container)) -> dict:
    user_id = require_user(app.settings, authorization)
    for field in ("district_id", "prakhand_id", "body_type", "body_id"):
        if not str(payload.get(field) or "").strip():
            raise AppError(f"{field} is required")
    result: IngestStart = app.ingest.start(
        user_id,
        str(payload["district_id"]),
        str(payload["prakhand_id"]),
        str(payload["body_type"]),
        str(payload["body_id"]),
    )
    return {"status": result.status, "job_id": result.job_id}


@router.get("/jobs")
def list_jobs(
    limit: int = 15,
    offset: int = 0,
    q: str = "",
    status: str = "",
    authorization: str | None = Header(default=None),
    app: Container = Depends(container),
) -> dict:
    require_user(app.settings, authorization)
    return app.jobs.list_jobs(limit, offset, q, status)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, authorization: str | None = Header(default=None), app: Container = Depends(container)) -> dict:
    require_user(app.settings, authorization)
    progress = app.jobs.job_progress(job_id)
    job = progress.get("job")
    if not job:
        raise AppError("Job not found", 404)
    return {
        "id": job["id"],
        "status": job["status"],
        "error": job["error"],
        "district_id": job["district_id"],
        "district_name": job["district_name"],
        "prakhand_id": job["prakhand_id"],
        "prakhand_name": job["prakhand_name"],
        "body_type": job["body_type"],
        "body_id": job["body_id"],
        "body_name": job["body_name"],
        "publication": job["publication"],
        "voter_count": progress["voter_count"],
        "files": [
            {
                "ward_no": item["ward_no"],
                "status": item["status"],
                "page_count": item["page_count"],
                "pages_ready": item["pages_ready"],
                "voter_count": item["voter_count"],
                "error": item["error"],
            }
            for item in progress["files"]
        ],
    }


@router.get("/wards")
def wards(
    district_id: str,
    prakhand_id: str,
    body_type: str,
    body_id: str,
    authorization: str | None = Header(default=None),
    app: Container = Depends(container),
) -> dict:
    require_user(app.settings, authorization)
    body = app.catalog.get_body(district_id, prakhand_id, body_type, body_id)
    table = _table(app, "voters")
    rows = app.rolls.query(
        f"""
        select distinct ward_no
        from {table}
        where publication = @publication
          and district = @district
          and prakhand = @prakhand
          and body_type = @body_type
          and body_name = @body_name
          and ward_no is not null
        order by ward_no
        """,
        _place_params(body),
    )
    return {"wards": [int(row["ward_no"]) for row in rows if row.get("ward_no") is not None]}


@router.get("/voter-fields")
def voter_fields(authorization: str | None = Header(default=None), app: Container = Depends(container)) -> dict:
    require_user(app.settings, authorization)
    return fields_payload()


@router.post("/voters/mark")
def mark_voter(
    payload: dict,
    authorization: str | None = Header(default=None),
    app: Container = Depends(container),
) -> dict:
    require_user(app.settings, authorization)
    mark = clean_mark(payload)
    app.rolls.save_mark(mark)
    return mark_public(mark)


@router.get("/voters")
def voters(
    district_id: str,
    prakhand_id: str,
    body_type: str,
    body_id: str,
    request: Request,
    ward_no: int | None = None,
    q: str = "",
    sort: str = "",
    direction: str = "asc",
    limit: int = 24,
    offset: int = 0,
    authorization: str | None = Header(default=None),
    app: Container = Depends(container),
) -> dict:
    require_user(app.settings, authorization)
    body = app.catalog.get_body(district_id, prakhand_id, body_type, body_id)
    bounded = min(max(limit, 1), 100)
    start = max(offset, 0)
    from adapters.roll_store import int_param

    where = """
        v.publication = @publication
        and v.district = @district
        and v.prakhand = @prakhand
        and v.body_type = @body_type
        and v.body_name = @body_name
    """
    params = _place_params(body)
    if ward_no is not None:
        where += " and v.ward_no = @ward_no"
        params.append(int_param("ward_no", ward_no))
    needle = q.strip().replace("%", "").replace("_", "")[:80]
    if needle:
        clause, extra = voter_search(needle)
        where += f" and ({clause})"
        params.extend(extra)
    filters = {key: request.query_params.get(key, "") for key in FILTER_KEYS}
    filter_sql, filter_params = extra_where(filters)
    if filter_sql:
        where += f" and {filter_sql}"
        params.extend(filter_params)
    source = f"{_table(app, 'voters')} v left join {_table(app, 'voter_marks')} m on m.voter_key = {VOTER_KEY_SQL}"
    rows = app.rolls.query(
        f"""
        select v.serial, v.epic, v.name, v.relation, v.relation_name, v.house_no, {AGE_SQL} as age, v.gender,
               v.assembly_ref, v.part_no, v.ward_no, v.booth_no, {VOTER_KEY_SQL} as voter_key,
               m.religion, m.caste, m.category, m.occupation, m.farmer_kinds, m.farmer_other,
               m.shop_kinds, m.shop_other, m.occupation_other, m.ideology, m.leader,
               count(*) over() as match_count
        from {source}
        where {where}
        order by {order_clause(sort, direction)}
        limit @limit offset @offset
        """,
        [*params, int_param("limit", bounded), int_param("offset", start)],
    )
    total = int(rows[0]["match_count"]) if rows else 0
    return {
        "body_name": body.body_name,
        "ward_no": ward_no,
        "total": total,
        "voters": [present_voter(row) for row in rows],
    }


def _table(app: Container, name: str) -> str:
    project = app.settings.gcp_project_id
    dataset = app.settings.bigquery_dataset
    return f"`{project}.{dataset}.{name}`"


def _place_params(body) -> list[dict]:
    from adapters.roll_store import string_param

    return [
        string_param("publication", body.publication),
        string_param("district", body.district_name),
        string_param("prakhand", body.prakhand_name),
        string_param("body_type", body.body_type),
        string_param("body_name", body.body_name),
    ]


worker = APIRouter()


@worker.post("/internal/qstash/{step}")
async def qstash_step(step: str, request: Request, app: Container = Depends(container)) -> dict:
    if step not in {"discover", "file", "page", "booth"}:
        raise AppError("Unknown worker step", 404)
    raw = await request.body()
    try:
        message = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError("Worker payload is not JSON", 400) from exc
    url = f"{str(message.get('callback_base', '')).rstrip('/')}{request.url.path}"
    app.queue.verify(request.headers.get("upstash-signature", ""), raw, url)
    log.info("worker %s %s", step, message.get("job_id"))
    if step == "discover":
        app.pipeline.discover(message)
    elif step == "file":
        app.pipeline.store_file(message)
    elif step == "page":
        app.pipeline.read_page(message)
    else:
        app.pipeline.assign_split_ward(message)
    return {"ok": True}
