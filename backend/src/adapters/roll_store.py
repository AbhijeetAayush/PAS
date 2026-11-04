from __future__ import annotations

import base64
import json
import time

import httpx
import jwt


class GoogleAuth:
    def __init__(self, service_account_b64: str) -> None:
        raw = base64.b64decode(service_account_b64)
        self.info = json.loads(raw)
        self._token = ""
        self._expiry = 0

    def token(self) -> str:
        if self._token and time.time() < self._expiry - 60:
            return self._token
        issued = int(time.time())
        assertion = jwt.encode(
            {
                "iss": self.info["client_email"],
                "scope": "https://www.googleapis.com/auth/cloud-platform",
                "aud": self.info.get("token_uri", "https://oauth2.googleapis.com/token"),
                "iat": issued,
                "exp": issued + 3600,
            },
            self.info["private_key"],
            algorithm="RS256",
        )
        response = httpx.post(
            self.info.get("token_uri", "https://oauth2.googleapis.com/token"),
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        self._token = body["access_token"]
        self._expiry = issued + int(body.get("expires_in", 3600))
        return self._token


class RollStore:
    def __init__(self, auth: GoogleAuth, project: str, dataset: str, location: str) -> None:
        self.auth = auth
        self.project = project
        self.dataset = dataset
        self.location = location
        self._ready = False

    def ensure(self) -> None:
        if self._ready:
            return
        self._post(
            f"https://bigquery.googleapis.com/bigquery/v2/projects/{self.project}/datasets",
            {
                "datasetReference": {"projectId": self.project, "datasetId": self.dataset},
                "location": self.location,
            },
            allow=(409,),
        )
        for name, fields in _TABLES.items():
            self._post(
                f"https://bigquery.googleapis.com/bigquery/v2/projects/{self.project}/datasets/{self.dataset}/tables",
                {
                    "tableReference": {
                        "projectId": self.project,
                        "datasetId": self.dataset,
                        "tableId": name,
                    },
                    "schema": {"fields": fields},
                },
                allow=(409,),
            )
        marks = f"`{self.project}.{self.dataset}.voter_marks`"
        self._post(
            f"https://bigquery.googleapis.com/bigquery/v2/projects/{self.project}/queries",
            {
                "query": (
                    f"alter table {marks} "
                    "add column if not exists ideology STRING, "
                    "add column if not exists leader STRING"
                ),
                "useLegacySql": False,
                "defaultDataset": {"projectId": self.project, "datasetId": self.dataset},
            },
        )
        self._ready = True

    def insert_voters(self, rows: list[dict]) -> None:
        if not rows:
            return
        self.ensure()
        self._insert("voters", rows)

    def insert_ward(self, row: dict) -> None:
        self.ensure()
        self._insert("ward_rolls", [row])

    def save_mark(self, mark: dict) -> None:
        self.ensure()
        table = f"`{self.project}.{self.dataset}.voter_marks`"
        fields = (
            "religion",
            "caste",
            "category",
            "occupation",
            "farmer_kinds",
            "farmer_other",
            "shop_kinds",
            "shop_other",
            "occupation_other",
            "ideology",
            "leader",
        )
        assignments = ", ".join(f"{name} = nullif(@{name}, '')" for name in fields)
        columns = ", ".join(("voter_key", *fields, "updated_at"))
        values = ", ".join(("@voter_key", *(f"nullif(@{name}, '')" for name in fields), "current_timestamp()"))
        self.query(
            f"""
            merge {table} t
            using (select @voter_key as voter_key) s
            on t.voter_key = s.voter_key
            when matched then update set {assignments}, updated_at = current_timestamp()
            when not matched then insert ({columns}) values ({values})
            """,
            [string_param("voter_key", mark["voter_key"]), *[string_param(name, mark[name]) for name in fields]],
        )

    def query(self, sql: str, params: list[dict]) -> list[dict]:
        self.ensure()
        response = self._post(
            f"https://bigquery.googleapis.com/bigquery/v2/projects/{self.project}/queries",
            {
                "query": sql,
                "useLegacySql": False,
                "parameterMode": "NAMED",
                "queryParameters": params,
                "defaultDataset": {"projectId": self.project, "datasetId": self.dataset},
            },
        )
        fields = [field["name"] for field in response.get("schema", {}).get("fields", [])]
        records = []
        for row in response.get("rows", []):
            values = [cell.get("v") for cell in row["f"]]
            records.append(dict(zip(fields, values, strict=True)))
        return records

    def _insert(self, table: str, rows: list[dict]) -> None:
        payload_rows = []
        for row in rows:
            item = dict(row)
            insert_id = str(item.pop("_insert_id"))
            payload_rows.append({"insertId": insert_id, "json": item})
        payload = {"rows": payload_rows}
        self._post(
            "https://bigquery.googleapis.com/bigquery/v2/projects/"
            f"{self.project}/datasets/{self.dataset}/tables/{table}/insertAll",
            payload,
        )

    def _post(self, url: str, payload: dict, allow: tuple[int, ...] = ()) -> dict:
        response = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {self.auth.token()}"},
            timeout=60,
        )
        if response.status_code in allow:
            return {}
        if response.status_code >= 400:
            raise RuntimeError(f"BigQuery {response.status_code}: {response.text[:500]}")
        if not response.content:
            return {}
        body = response.json()
        errors = body.get("insertErrors") if isinstance(body, dict) else None
        if errors:
            raise RuntimeError(f"BigQuery insert failed: {errors[:2]}")
        return body


def string_param(name: str, value: str) -> dict:
    return {"name": name, "parameterType": {"type": "STRING"}, "parameterValue": {"value": value}}


def int_param(name: str, value: int) -> dict:
    return {"name": name, "parameterType": {"type": "INT64"}, "parameterValue": {"value": str(value)}}


_PLACE = [
    {"name": "publication", "type": "STRING"},
    {"name": "district", "type": "STRING"},
    {"name": "prakhand", "type": "STRING"},
    {"name": "body_type", "type": "STRING"},
    {"name": "body_name", "type": "STRING"},
    {"name": "ward_no", "type": "INT64"},
    {"name": "part_no", "type": "INT64"},
    {"name": "source_url", "type": "STRING"},
    {"name": "ingested_at", "type": "TIMESTAMP"},
]

_TABLES = {
    "voters": [
        *[{"name": item["name"], "type": item["type"], "mode": "NULLABLE"} for item in _PLACE[:7]],
        {"name": "serial", "type": "INT64", "mode": "REQUIRED"},
        {"name": "epic", "type": "STRING", "mode": "NULLABLE"},
        {"name": "name", "type": "STRING", "mode": "REQUIRED"},
        {"name": "relation", "type": "STRING", "mode": "NULLABLE"},
        {"name": "relation_name", "type": "STRING", "mode": "NULLABLE"},
        {"name": "house_no", "type": "STRING", "mode": "NULLABLE"},
        {"name": "age", "type": "STRING", "mode": "NULLABLE"},
        {"name": "gender", "type": "STRING", "mode": "NULLABLE"},
        {"name": "assembly_ref", "type": "STRING", "mode": "NULLABLE"},
        {"name": "source_url", "type": "STRING", "mode": "NULLABLE"},
        {"name": "page_no", "type": "INT64", "mode": "NULLABLE"},
        {"name": "ingested_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ],
    "ward_rolls": [
        {"name": item["name"], "type": item["type"], "mode": "NULLABLE"}
        for item in [
            *_PLACE,
            {"name": "male_count", "type": "INT64"},
            {"name": "female_count", "type": "INT64"},
            {"name": "total_count", "type": "INT64"},
        ]
    ],
    "voter_marks": [
        {"name": "voter_key", "type": "STRING", "mode": "REQUIRED"},
        {"name": "religion", "type": "STRING", "mode": "NULLABLE"},
        {"name": "caste", "type": "STRING", "mode": "NULLABLE"},
        {"name": "category", "type": "STRING", "mode": "NULLABLE"},
        {"name": "occupation", "type": "STRING", "mode": "NULLABLE"},
        {"name": "farmer_kinds", "type": "STRING", "mode": "NULLABLE"},
        {"name": "farmer_other", "type": "STRING", "mode": "NULLABLE"},
        {"name": "shop_kinds", "type": "STRING", "mode": "NULLABLE"},
        {"name": "shop_other", "type": "STRING", "mode": "NULLABLE"},
        {"name": "occupation_other", "type": "STRING", "mode": "NULLABLE"},
        {"name": "ideology", "type": "STRING", "mode": "NULLABLE"},
        {"name": "leader", "type": "STRING", "mode": "NULLABLE"},
        {"name": "updated_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ],
}
