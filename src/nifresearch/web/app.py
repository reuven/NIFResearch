from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from nifresearch.models import Classification, SourceStatus
from nifresearch.orchestrator import run_streaming
from nifresearch.registry_setup import build_default_registry
from nifresearch.resolution import build_profile
from nifresearch.web.params import build_request_context

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="NIFResearch")


def render_report_fragment(profile, registry_map: dict[str, str], grey_ids: set[str]) -> str:
    grey_ran = any(
        r.source_id in grey_ids and r.status != SourceStatus.SKIPPED
        for r in profile.results
    )
    template = TEMPLATES.env.get_template("_report_body.html")
    return template.render(
        groups=profile.by_type(), results=profile.results,
        registry=registry_map, grey_ran=grey_ran,
    )


@app.get("/", response_class=HTMLResponse)
async def form(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "form.html", {})


@app.post("/research", response_class=HTMLResponse)
async def research(
    request: Request,
    name_he: str | None = Form(default=None),
    name_en: str | None = Form(default=None),
    email: str | None = Form(default=None),
    phone: str | None = Form(default=None),
    id_number: str | None = Form(default=None),
    compliance_mode: str | None = Form(default=None),
) -> HTMLResponse:
    subject, warnings, _mode = build_request_context(
        name_he, name_en, email, phone, id_number, compliance_mode
    )
    registry = build_default_registry()
    rows = [{"id": s.id, "name": s.name} for s in registry.all()]
    params = {
        "name_he": name_he, "name_en": name_en, "email": email,
        "phone": phone, "id_number": id_number, "compliance_mode": compliance_mode,
    }
    stream_url = "/research/stream?" + urlencode(
        {k: v for k, v in params.items() if v}
    )
    return TEMPLATES.TemplateResponse(
        request,
        "research.html",
        {"warnings": warnings, "rows": rows, "stream_url": stream_url},
    )


@app.get("/research/stream")
async def research_stream(
    name_he: str | None = None,
    name_en: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    id_number: str | None = None,
    compliance_mode: str | None = None,
) -> StreamingResponse:
    subject, _warnings, mode = build_request_context(
        name_he, name_en, email, phone, id_number, compliance_mode
    )

    async def event_stream():
        async with httpx.AsyncClient() as client:
            registry = build_default_registry(client)
            sources = registry.all()
            registry_map = {s.id: s.name for s in sources}
            grey_ids = {s.id for s in sources if s.classification == Classification.GREY_MARKET}
            results = []
            async for result in run_streaming(subject, sources, mode):
                results.append(result)
                payload = {
                    "source_id": result.source_id,
                    "name": registry_map.get(result.source_id, result.source_id),
                    "status": result.status.value,
                    "fact_count": len(result.facts),
                }
                yield f"event: progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            profile = build_profile(subject, results)
            html = render_report_fragment(profile, registry_map, grey_ids)
            yield f"event: done\ndata: {json.dumps({'html': html}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
