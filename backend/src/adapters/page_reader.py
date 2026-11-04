from __future__ import annotations

import base64
import io
import json
from typing import Protocol

import httpx

from domain.cards import clean_page
from domain.models import AppError

_PROMPT = """
Read this one page of a Bihar municipal or panchayat voter roll.
The embedded PDF text is unreliable. Read the visible letters in the image.
Copy Hindi exactly as printed. Do not translate and do not transliterate.
A card page is a grid of voter boxes. For each box return:
serial, epic, name (निर्वाचक का नाम), relation (पिता, पति, माता, or अन्य),
relation_name, house_no (गृह संख्या), age (उम्र, as printed), gender (लिंग, as printed),
assembly_ref (the number like 157/130/317).
page_kind is "cover" for the summary sheet and "voters" for card pages.
On a cover page, voters is empty and male_count, female_count, total_count, ward_no, part_no
are the printed totals. On a card page, fill ward_no and part_no from the page header.
""".strip()


def render_page(pdf: bytes, page_no: int) -> bytes:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf)
    try:
        if page_no < 1 or page_no > len(document):
            raise AppError(f"Page {page_no} is outside this PDF", 400)
        bitmap = document[page_no - 1].render(scale=2)
        image = bitmap.to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    finally:
        document.close()


def page_count(pdf: bytes) -> int:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf)
    try:
        return len(document)
    finally:
        document.close()


class TokenSource(Protocol):
    def token(self) -> str: ...


class PageReader:
    def __init__(self, auth: TokenSource, model: str, project: str, location: str) -> None:
        self.auth = auth
        self.model = model
        self.project = project
        self.location = location

    def read_page(self, image: bytes, ward_hint: int | None) -> dict:
        hint = f"The file name says ward {ward_hint}." if ward_hint else ""
        url = _vertex_url(self.model, self.project, self.location)
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.auth.token()}"},
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": f"{_PROMPT}\n{hint}"},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": base64.b64encode(image).decode(),
                                }
                            },
                        ],
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": 32768,
                    "responseMimeType": "application/json",
                    "thinkingConfig": {"thinkingLevel": "MINIMAL"},
                },
            },
            timeout=120,
        )
        if response.status_code >= 400:
            raise AppError(f"Vertex read failed: {response.status_code} {response.text[:300]}", 502)
        body = response.json()
        text = _response_text(body)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AppError("Vertex returned unreadable JSON", 502) from exc
        return clean_page(_as_page(payload))


def _as_page(payload: object) -> dict:
    # Gemini sometimes wraps the one page object in a JSON array.
    if isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]
        if len(items) == 1 and ("voters" in items[0] or "page_kind" in items[0]):
            payload = items[0]
        elif items and all("name" in item or "serial" in item for item in items):
            payload = {"page_kind": "voters", "voters": items}
    if not isinstance(payload, dict):
        raise AppError("Vertex returned an unexpected page shape", 502)
    return payload


def _vertex_url(model: str, project: str, location: str) -> str:
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return (
        f"https://{host}/v1/projects/{project}/locations/{location}"
        f"/publishers/google/models/{model}:generateContent"
    )


def _response_text(body: dict) -> str:
    candidates = body.get("candidates") or []
    if not candidates:
        raise AppError("Vertex returned no reading of the page", 502)
    finish = str(candidates[0].get("finishReason") or "")
    if finish and finish not in {"STOP", "FINISH_REASON_UNSPECIFIED"}:
        raise AppError(f"Vertex stopped early: {finish}", 502)
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    if not text:
        raise AppError("Vertex returned an empty reading", 502)
    return text
