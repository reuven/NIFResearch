from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from nifresearch.orchestrator import run
from nifresearch.registry_setup import build_default_registry
from nifresearch.resolution import build_profile
from nifresearch.web.params import build_request_context

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="NIFResearch")


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
    subject, warnings, mode = build_request_context(
        name_he, name_en, email, phone, id_number, compliance_mode
    )
    async with httpx.AsyncClient() as client:
        registry = build_default_registry(client)
        sources = registry.all()
        results = await run(subject, sources, mode)
        registry_map = {s.id: s.name for s in sources}
    profile = build_profile(subject, results)
    return TEMPLATES.TemplateResponse(
        request,
        "report.html",
        {
            "subject": subject,
            "warnings": warnings,
            "groups": profile.by_type(),
            "results": profile.results,
            "registry": registry_map,
        },
    )
