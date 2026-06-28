# NIFResearch v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make searches return real, useful results (drop fake/broken sources, add the doctors registry), add a strictness dropdown, and show live per-source progress via SSE.

**Architecture:** Replace the mock and broken-Bar sources with a working data.gov.il doctors source. The web layer renders a progress page that opens an `EventSource` to a streaming endpoint; the orchestrator gains a `run_streaming` async generator that yields each source's result as it completes; the final SSE event delivers the rendered report fragment.

**Tech Stack:** Python 3.14, uv, Pydantic v2, FastAPI (StreamingResponse + SSE), httpx, Jinja2, pytest, pytest-asyncio, respx.

## Global Constraints

- Python `>=3.14`; manage with `uv` (`uv run …`).
- No persistence: results are per-request/ephemeral; no DB, no job store.
- Every `Fact` carries provenance: `source_id`, `confidence`, and `url` pointing to the actual retrieval source (the data.gov.il dataset page).
- Default compliance mode is **STRICT**; the dropdown may select STANDARD/PERMISSIVE but all current sources are `official_public`.
- All source HTTP goes through the shared `CkanClient`; tests mock HTTP with `respx` (never the network).
- Hebrew/RTL: templates set `dir="rtl"` and `lang="he"`.
- SSE `data:` payloads are JSON on a single line (HTML is JSON-encoded; the JS parses it).
- TDD throughout: failing test → minimal code → passing test → commit. Run `uv run pytest` for the suite.

---

## File Structure

- Create `src/nifresearch/sources/datagov_doctors.py` — MoH doctors source.
- Create `src/nifresearch/web/params.py` — request-param helpers (compliance parse + context build).
- Create `src/nifresearch/web/templates/_report_body.html` — report fragment.
- Create `src/nifresearch/web/templates/research.html` — progress page + SSE JS.
- Modify `src/nifresearch/orchestrator.py` — `_gate`/`_execute` refactor, `run_streaming`, timeout 25s.
- Modify `src/nifresearch/registry_setup.py` — registry = Amutot + Companies + Doctors.
- Modify `src/nifresearch/web/app.py` — parsed compliance mode, progress page, SSE stream.
- Modify `src/nifresearch/web/templates/form.html` — strictness dropdown.
- Delete `src/nifresearch/sources/mock.py`, `tests/test_mock_source.py`.
- Delete `src/nifresearch/sources/bar_lawyers.py`, `tests/test_bar_lawyers.py`.
- Delete `src/nifresearch/web/templates/report.html` (in Task 6, once SSE delivers the fragment).
- Tests: `tests/test_datagov_doctors.py`, additions to `tests/test_orchestrator.py`, `tests/test_web_params.py`, rebuild `tests/test_web.py`, update `tests/test_registry_setup.py`.

---

### Task 1: DoctorsSource

**Files:**
- Create: `src/nifresearch/sources/datagov_doctors.py`
- Test: `tests/test_datagov_doctors.py`

**Interfaces:**
- Consumes: `Source` (`sources.base`), `CkanClient` (`sources.ckan`), models.
- Produces: `class DoctorsSource(Source)` — id `"datagov_doctors"`, classification `OFFICIAL_PUBLIC`, required_inputs `{InputField.NAME}`, `__init__(self, client: httpx.AsyncClient | None = None)`. Constants `BASE_URL="https://data.gov.il"`, `RESOURCE_ID="9c64c522-bbc2-48fe-96fb-3b2a8626f59e"`. `query` searches by name; each record yields a `PROFESSION` fact (value `"רופא/ה"`) and a `LICENSE` fact, both with `detail["license_number"]` (`"מספר רישיון רופא"`), `detail["specialty"]` (`"שם התמחות"`), `detail["full_name"]` (`"שם פרטי"` + `"שם משפחה"`), `confidence=0.4`, `url="https://data.gov.il/dataset/database-of-doctors-licenses-moh"`. `NO_MATCH` when no records.

- [ ] **Step 1: Write the failing test**

`tests/test_datagov_doctors.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.datagov_doctors import DoctorsSource


def test_metadata():
    src = DoctorsSource()
    assert src.id == "datagov_doctors"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
@respx.mock
async def test_query_maps_record_to_profession_and_license():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": [
            {"שם פרטי": "דוד", "שם משפחה": "כהן",
             "מספר רישיון רופא": 12345, "שם התמחות": "קרדיולוגיה"},
        ]}})
    )
    async with httpx.AsyncClient() as client:
        result = await DoctorsSource(client=client).query(Subject(name_he="דוד כהן"))
    assert result.status == SourceStatus.OK
    types = {f.type for f in result.facts}
    assert FactType.PROFESSION in types
    assert FactType.LICENSE in types
    prof = next(f for f in result.facts if f.type == FactType.PROFESSION)
    assert prof.value == "רופא/ה"
    assert prof.confidence == 0.4
    assert prof.url == "https://data.gov.il/dataset/database-of-doctors-licenses-moh"
    assert prof.detail["specialty"] == "קרדיולוגיה"
    assert prof.detail["license_number"] == "12345"
    assert prof.detail["full_name"] == "דוד כהן"


@pytest.mark.asyncio
@respx.mock
async def test_query_no_records_is_no_match():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    async with httpx.AsyncClient() as client:
        result = await DoctorsSource(client=client).query(Subject(name_he="איןכזה"))
    assert result.status == SourceStatus.NO_MATCH
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datagov_doctors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.sources.datagov_doctors'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/sources/datagov_doctors.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source
from nifresearch.sources.ckan import CkanClient

BASE_URL = "https://data.gov.il"
RESOURCE_ID = "9c64c522-bbc2-48fe-96fb-3b2a8626f59e"
DATASET_URL = "https://data.gov.il/dataset/database-of-doctors-licenses-moh"


class DoctorsSource(Source):
    id = "datagov_doctors"
    name = "data.gov.il — Doctors registry (MoH)"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._ckan = CkanClient(BASE_URL, client=client)

    async def query(self, subject: Subject) -> SourceResult:
        name = subject.name_he or subject.name_en
        if not name:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        records = await self._ckan.datastore_search(RESOURCE_ID, q=name, limit=10)
        if not records:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        facts: list[Fact] = []
        for rec in records:
            full_name = f"{rec.get('שם פרטי', '')} {rec.get('שם משפחה', '')}".strip()
            detail = {
                "license_number": str(rec.get("מספר רישיון רופא", "")),
                "specialty": rec.get("שם התמחות", ""),
                "full_name": full_name,
            }
            facts.append(Fact(
                type=FactType.PROFESSION, value="רופא/ה",
                source_id=self.id, confidence=0.4, url=DATASET_URL, detail=dict(detail),
            ))
            facts.append(Fact(
                type=FactType.LICENSE,
                value=f"רישיון רופא {detail['license_number']}".strip(),
                source_id=self.id, confidence=0.4, url=DATASET_URL, detail=dict(detail),
            ))
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datagov_doctors.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/sources/datagov_doctors.py tests/test_datagov_doctors.py
git commit -m "feat: data.gov.il doctors registry source"
```

---

### Task 2: Orchestrator — gate/execute split, run_streaming, timeout 25s

**Files:**
- Modify: `src/nifresearch/orchestrator.py`
- Test: `tests/test_orchestrator.py` (add tests; keep existing)

**Interfaces:**
- Consumes: `is_allowed`, `Source`, models.
- Produces (additions):
  - `async def run_streaming(subject: Subject, sources: list[Source], mode: ComplianceMode, timeout: float = 25.0) -> AsyncIterator[SourceResult]` — yields one `SourceResult` per source: skipped ones immediately, eligible ones as each finishes.
  - `run(...)` default `timeout` raised to `25.0`. Internal helpers `_gate(source, subject, mode) -> SourceResult | None` and `async _execute(source, subject, timeout) -> SourceResult`.

- [ ] **Step 1: Write the failing test (append to `tests/test_orchestrator.py`)**

Add these imports at the top if missing: `from nifresearch.orchestrator import run, run_streaming`. Append:
```python
@pytest.mark.asyncio
async def test_run_streaming_yields_one_result_per_source_including_skipped():
    subject = Subject(name_he="דוד")
    sources = [OkSource(), LicensedSource(), BoomSource()]
    results = [r async for r in run_streaming(subject, sources, ComplianceMode.STRICT)]
    by_id = {r.source_id: r for r in results}
    assert set(by_id) == {"ok", "lic", "boom"}
    assert by_id["ok"].status == SourceStatus.OK
    assert by_id["lic"].status == SourceStatus.SKIPPED      # licensed blocked under STRICT
    assert by_id["boom"].status == SourceStatus.ERROR       # raises
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_orchestrator.py::test_run_streaming_yields_one_result_per_source_including_skipped -v`
Expected: FAIL with `ImportError: cannot import name 'run_streaming'`

- [ ] **Step 3: Rewrite `src/nifresearch/orchestrator.py`**

```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from nifresearch.compliance import is_allowed
from nifresearch.models import ComplianceMode, SourceResult, SourceStatus, Subject
from nifresearch.sources.base import Source


def _gate(source: Source, subject: Subject, mode: ComplianceMode) -> SourceResult | None:
    """Return a SKIPPED result if the source must not run, else None."""
    if not is_allowed(source.classification, mode):
        return SourceResult(
            source_id=source.id, status=SourceStatus.SKIPPED,
            error="blocked by compliance mode",
        )
    if not source.can_run(subject):
        return SourceResult(
            source_id=source.id, status=SourceStatus.SKIPPED,
            error="missing required inputs",
        )
    return None


async def _execute(source: Source, subject: Subject, timeout: float) -> SourceResult:
    try:
        return await asyncio.wait_for(source.query(subject), timeout)
    except (TimeoutError, asyncio.TimeoutError):
        return SourceResult(source_id=source.id, status=SourceStatus.ERROR, error="timed out")
    except Exception as exc:  # noqa: BLE001 — record any source failure
        return SourceResult(source_id=source.id, status=SourceStatus.ERROR, error=str(exc))


async def _run_one(source: Source, subject: Subject, mode: ComplianceMode, timeout: float) -> SourceResult:
    skipped = _gate(source, subject, mode)
    if skipped is not None:
        return skipped
    return await _execute(source, subject, timeout)


async def run(
    subject: Subject,
    sources: list[Source],
    mode: ComplianceMode,
    timeout: float = 25.0,
) -> list[SourceResult]:
    return await asyncio.gather(*(_run_one(s, subject, mode, timeout) for s in sources))


async def run_streaming(
    subject: Subject,
    sources: list[Source],
    mode: ComplianceMode,
    timeout: float = 25.0,
) -> AsyncIterator[SourceResult]:
    pending: list[asyncio.Task[SourceResult]] = []
    for source in sources:
        skipped = _gate(source, subject, mode)
        if skipped is not None:
            yield skipped
        else:
            pending.append(asyncio.ensure_future(_execute(source, subject, timeout)))
    for fut in asyncio.as_completed(pending):
        yield await fut
```

- [ ] **Step 4: Run the orchestrator tests**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: PASS (all existing tests + the new one)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator run_streaming generator and 25s timeout"
```

---

### Task 3: Web request-param helpers

**Files:**
- Create: `src/nifresearch/web/params.py`
- Test: `tests/test_web_params.py`

**Interfaces:**
- Consumes: `build_subject` (`intake`), `ComplianceMode`, `Subject`.
- Produces:
  - `def parse_compliance_mode(raw: str | None) -> ComplianceMode` — maps `"strict"/"standard"/"permissive"` (case-insensitive) to the enum; defaults to `STRICT` on `None`/unknown.
  - `def build_request_context(name_he, name_en, email, phone, id_number, compliance_mode) -> tuple[Subject, list[str], ComplianceMode]` — each arg `str | None`; returns `(subject, warnings, mode)`.

- [ ] **Step 1: Write the failing test**

`tests/test_web_params.py`:
```python
from nifresearch.models import ComplianceMode
from nifresearch.web.params import parse_compliance_mode, build_request_context


def test_parse_compliance_mode():
    assert parse_compliance_mode("standard") == ComplianceMode.STANDARD
    assert parse_compliance_mode("PERMISSIVE") == ComplianceMode.PERMISSIVE
    assert parse_compliance_mode("strict") == ComplianceMode.STRICT
    assert parse_compliance_mode(None) == ComplianceMode.STRICT
    assert parse_compliance_mode("garbage") == ComplianceMode.STRICT


def test_build_request_context():
    subject, warnings, mode = build_request_context(
        "דוד כהן", None, "d@e.co", None, "123456789", "standard"
    )
    assert subject.name_he == "דוד כהן"
    assert subject.email == "d@e.co"
    assert subject.id_number is None        # invalid ID dropped
    assert any("ID" in w or "ת\"ז" in w for w in warnings)
    assert mode == ComplianceMode.STANDARD
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_web_params.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.web.params'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/web/params.py`:
```python
from __future__ import annotations

from nifresearch.intake import build_subject
from nifresearch.models import ComplianceMode, Subject


def parse_compliance_mode(raw: str | None) -> ComplianceMode:
    if raw:
        try:
            return ComplianceMode(raw.strip().lower())
        except ValueError:
            pass
    return ComplianceMode.STRICT


def build_request_context(
    name_he: str | None,
    name_en: str | None,
    email: str | None,
    phone: str | None,
    id_number: str | None,
    compliance_mode: str | None,
) -> tuple[Subject, list[str], ComplianceMode]:
    subject, warnings = build_subject(name_he, name_en, email, phone, id_number)
    return subject, warnings, parse_compliance_mode(compliance_mode)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_web_params.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/web/params.py tests/test_web_params.py
git commit -m "feat: web request-param helpers (compliance parse, context build)"
```

---

### Task 4: Remove mock + Bar sources; register Doctors

**Files:**
- Delete: `src/nifresearch/sources/mock.py`, `tests/test_mock_source.py`
- Delete: `src/nifresearch/sources/bar_lawyers.py`, `tests/test_bar_lawyers.py`
- Modify: `src/nifresearch/registry_setup.py`
- Modify: `tests/test_registry_setup.py`
- Modify: `tests/test_web.py` (stop depending on the deleted mock; app.py stays synchronous here)

**Interfaces:**
- Consumes: `AmutotSource`, `CompaniesSource`, `DoctorsSource`, `SourceRegistry`.
- Produces: `build_default_registry(client=None)` registers, in order: `AmutotSource(client)`, `CompaniesSource(client)`, `DoctorsSource(client)`.

- [ ] **Step 1: Update the registry test (failing)**

Replace `tests/test_registry_setup.py`:
```python
from nifresearch.registry_setup import build_default_registry


def test_default_registry_contains_expected_sources():
    reg = build_default_registry()
    ids = [s.id for s in reg.all()]
    assert ids == ["datagov_amutot", "datagov_companies", "datagov_doctors"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_registry_setup.py -v`
Expected: FAIL (registry still includes `mock_board` / `bar_lawyers`)

- [ ] **Step 3: Rewrite `src/nifresearch/registry_setup.py`**

```python
from __future__ import annotations

import httpx

from nifresearch.sources.base import SourceRegistry
from nifresearch.sources.datagov_amutot import AmutotSource
from nifresearch.sources.datagov_companies import CompaniesSource
from nifresearch.sources.datagov_doctors import DoctorsSource


def build_default_registry(client: httpx.AsyncClient | None = None) -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(AmutotSource(client))
    registry.register(CompaniesSource(client))
    registry.register(DoctorsSource(client))
    return registry
```

- [ ] **Step 4: Delete the dead sources and their tests**

```bash
git rm src/nifresearch/sources/mock.py tests/test_mock_source.py
git rm src/nifresearch/sources/bar_lawyers.py tests/test_bar_lawyers.py
```

- [ ] **Step 5: Rebuild `tests/test_web.py` to not depend on the mock**

Replace `tests/test_web.py` (app.py is still the original synchronous version at this point — it posts to `/research` and renders `report.html`):
```python
import httpx
import respx
from fastapi.testclient import TestClient

from nifresearch.web.app import app


def test_form_renders():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'name="name_he"' in resp.text


@respx.mock
def test_research_renders_report_no_findings():
    # All data.gov.il sources return no records -> no_match for all three.
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד כהן"})
    assert resp.status_code == 200
    assert 'dir="rtl"' in resp.text
    # The three real sources appear in the status table
    assert "datagov_amutot" in resp.text or "Non-profits" in resp.text
    assert "Doctors" in resp.text or "datagov_doctors" in resp.text
```

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS — no references to deleted modules remain.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: drop mock+Bar sources, register doctors source"
```

---

### Task 5: Strictness dropdown + report fragment + parsed mode (synchronous)

**Files:**
- Modify: `src/nifresearch/web/templates/form.html`
- Create: `src/nifresearch/web/templates/_report_body.html`
- Modify: `src/nifresearch/web/templates/report.html` (include the fragment)
- Modify: `src/nifresearch/web/app.py` (accept `compliance_mode`, use `build_request_context`)
- Modify: `tests/test_web.py`

**Interfaces:**
- Consumes: `build_request_context` (`web.params`), `run`, `build_default_registry`, `build_profile`.
- Produces: `/research` accepts an extra `compliance_mode` form field and uses the parsed mode.

- [ ] **Step 1: Write the failing test (append to `tests/test_web.py`)**

```python
def test_form_has_compliance_dropdown():
    client = TestClient(app)
    resp = client.get("/")
    assert 'name="compliance_mode"' in resp.text
    assert "strict" in resp.text and "standard" in resp.text and "permissive" in resp.text


@respx.mock
def test_research_accepts_compliance_mode():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד", "compliance_mode": "standard"})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_web.py::test_form_has_compliance_dropdown -v`
Expected: FAIL (`name="compliance_mode"` not in form)

- [ ] **Step 3: Add the dropdown to `form.html`**

Replace the `<form>...</form>` block in `src/nifresearch/web/templates/form.html` with:
```html
  <form action="/research" method="post">
    <label for="name_he">שם (עברית)</label><input id="name_he" name="name_he">
    <label for="name_en">Name (English)</label><input id="name_en" name="name_en">
    <label for="email">אימייל / Email</label><input id="email" name="email">
    <label for="phone">טלפון / Phone</label><input id="phone" name="phone">
    <label for="id_number">תעודת זהות / ID</label><input id="id_number" name="id_number">
    <label for="compliance_mode">רמת מקורות / Source strictness</label>
    <select id="compliance_mode" name="compliance_mode">
      <option value="strict" selected>strict — מקורות ציבוריים רשמיים בלבד</option>
      <option value="standard">standard — + מקורות מורשים</option>
      <option value="permissive">permissive — כל המקורות</option>
    </select>
    <p class="note">הרחבת הרמה משפיעה רק כאשר קיימים מקורות מורשים/אפורים (אין כרגע).</p>
    <button type="submit">חפש</button>
  </form>
```

- [ ] **Step 4: Extract the report fragment**

Create `src/nifresearch/web/templates/_report_body.html`:
```html
{% if not groups %}
  <p>לא נמצאו ממצאים מהמקורות הזמינים.</p>
{% endif %}
{% for fact_type, facts in groups.items() %}
  <h2>{{ fact_type.value }}</h2>
  {% for f in facts %}
    <div class="fact">{{ f.value }}
      <span class="src">— מקור: {{ registry.get(f.source_id, f.source_id) }}
        (<code>{{ f.source_id }}</code>) (ביטחון {{ "%.1f"|format(f.confidence) }}){% if f.url %},
        <a href="{{ f.url }}">קישור</a>{% endif %}</span>
    </div>
  {% endfor %}
{% endfor %}
<h2>מקורות שנבדקו</h2>
<table>
  <tr><th>מקור</th><th>סטטוס</th><th>הערה</th></tr>
  {% for r in results %}
    <tr>
      <td>{{ registry.get(r.source_id, r.source_id) }}</td>
      <td class="{{ r.status.value }}">{{ r.status.value }}</td>
      <td>{{ r.error or "" }}</td>
    </tr>
  {% endfor %}
</table>
<p class="src">תוצאות אינן נשמרות. למטרות מחקר תורמים בלבד.</p>
```

Replace the body of `src/nifresearch/web/templates/report.html` so the report content comes from the fragment:
```html
<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>דוח — NIFResearch</title>
  <style>
    body { font-family: sans-serif; max-width: 760px; margin: 2rem auto; }
    .warn { background:#fff3cd; padding:.5rem .75rem; border:1px solid #ffe69c; margin:.25rem 0; }
    .fact { padding:.35rem 0; border-bottom:1px solid #eee; }
    .src { color:#666; font-size:.8rem; }
    table { width:100%; border-collapse:collapse; margin-top:1rem; }
    td, th { border:1px solid #ddd; padding:.35rem; text-align:right; font-size:.9rem; }
    .skipped { color:#999; } .error { color:#b00; } .ok { color:#070; }
  </style>
</head>
<body>
  <h1>דוח מחקר</h1>
  {% for w in warnings %}<div class="warn">{{ w }}</div>{% endfor %}
  {% include "_report_body.html" %}
  <p><a href="/">חיפוש חדש</a></p>
</body>
</html>
```

- [ ] **Step 5: Update `app.py` to accept and use the compliance mode**

Replace the `research` handler in `src/nifresearch/web/app.py`. Change imports: remove `from nifresearch.models import ComplianceMode`, add `from nifresearch.web.params import build_request_context`. New handler:
```python
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
```

- [ ] **Step 6: Run the web tests, then the full suite**

Run: `uv run pytest tests/test_web.py -v` then `uv run pytest -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: strictness dropdown, parsed compliance mode, report fragment"
```

---

### Task 6: Live per-source progress via SSE

**Files:**
- Create: `src/nifresearch/web/templates/research.html`
- Modify: `src/nifresearch/web/app.py` (render progress page from `/research`; add `/research/stream`)
- Delete: `src/nifresearch/web/templates/report.html`
- Modify: `tests/test_web.py`

**Interfaces:**
- Consumes: `run_streaming`, `build_request_context`, `build_default_registry`, `build_profile`, `TEMPLATES`.
- Produces: `GET /research/stream` SSE endpoint; `render_report_fragment(profile, registry_map) -> str`; `/research` renders `research.html`.

- [ ] **Step 1: Write the failing tests (replace the body of `tests/test_web.py`)**

```python
from urllib.parse import quote

import httpx
import respx
from fastapi.testclient import TestClient

from nifresearch.web.app import app


def test_form_renders_with_dropdown():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'name="name_he"' in resp.text
    assert 'name="compliance_mode"' in resp.text


def test_research_returns_progress_page():
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד כהן"})
    assert resp.status_code == 200
    # progress page lists the real sources and wires up the SSE stream
    assert "/research/stream" in resp.text
    assert "Doctors" in resp.text or "datagov_doctors" in resp.text
    assert 'dir="rtl"' in resp.text


@respx.mock
def test_stream_emits_progress_and_done_with_fact():
    def responder(request):
        rid = request.url.params.get("resource_id")
        if rid == "9c64c522-bbc2-48fe-96fb-3b2a8626f59e":  # doctors
            return httpx.Response(200, json={"success": True, "result": {"records": [
                {"שם פרטי": "דוד", "שם משפחה": "כהן",
                 "מספר רישיון רופא": 123, "שם התמחות": "קרדיולוגיה"},
            ]}})
        return httpx.Response(200, json={"success": True, "result": {"records": []}})

    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(side_effect=responder)
    client = TestClient(app)
    resp = client.get("/research/stream?name_he=" + quote("דוד כהן"))
    assert resp.status_code == 200
    body = resp.text
    assert "event: progress" in body
    assert "event: done" in body
    assert "datagov_doctors" in body
    assert "רופא/ה" in body  # the doctor profession fact is in the done fragment
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_web.py -v`
Expected: FAIL (`/research/stream` 404 / progress page assertions fail)

- [ ] **Step 3: Create the progress page `research.html`**

`src/nifresearch/web/templates/research.html`:
```html
<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>דוח — NIFResearch</title>
  <style>
    body { font-family: sans-serif; max-width: 760px; margin: 2rem auto; }
    .warn { background:#fff3cd; padding:.5rem .75rem; border:1px solid #ffe69c; margin:.25rem 0; }
    .fact { padding:.35rem 0; border-bottom:1px solid #eee; }
    .src { color:#666; font-size:.8rem; }
    table { width:100%; border-collapse:collapse; margin-top:1rem; }
    td, th { border:1px solid #ddd; padding:.35rem; text-align:right; font-size:.9rem; }
    .skipped { color:#999; } .error { color:#b00; } .ok { color:#070; }
    #barwrap { background:#eee; border-radius:4px; height:14px; margin:1rem 0; overflow:hidden; }
    #bar { background:#070; height:100%; width:0; transition:width .3s; }
    #sources { list-style:none; padding:0; }
    #sources li { padding:.3rem 0; border-bottom:1px solid #f0f0f0; }
    #sources li .st { display:inline-block; width:2.5rem; font-weight:bold; }
  </style>
</head>
<body>
  <h1>מחקר תורמים — מתבצע…</h1>
  {% for w in warnings %}<div class="warn">{{ w }}</div>{% endfor %}
  <noscript>הצגת התקדמות חיה דורשת JavaScript.</noscript>
  <div id="barwrap"><div id="bar"></div></div>
  <ul id="sources">
    {% for row in rows %}
      <li data-id="{{ row.id }}"><span class="st">⋯</span>{{ row.name }}</li>
    {% endfor %}
  </ul>
  <div id="report"></div>
  <p><a href="/">חיפוש חדש</a></p>
  <script>
    const total = {{ rows|length }} || 1;
    let done = 0;
    const es = new EventSource({{ stream_url|tojson }});
    es.addEventListener('progress', (e) => {
      const d = JSON.parse(e.data);
      const li = document.querySelector('#sources li[data-id="' + d.source_id + '"]');
      if (li) {
        li.className = d.status;
        const mark = d.status === 'ok' ? ('✓ ' + d.fact_count)
                   : d.status === 'error' ? '✗'
                   : d.status === 'no_match' ? '–' : '⤳';
        li.querySelector('.st').textContent = mark;
      }
      done += 1;
      document.getElementById('bar').style.width = Math.round(100 * done / total) + '%';
    });
    es.addEventListener('done', (e) => {
      const d = JSON.parse(e.data);
      document.getElementById('report').innerHTML = d.html;
      document.getElementById('bar').style.width = '100%';
      es.close();
    });
    es.onerror = () => es.close();
  </script>
</body>
</html>
```

- [ ] **Step 4: Rewrite `app.py` for the progress page + SSE stream**

Full `src/nifresearch/web/app.py`:
```python
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from nifresearch.orchestrator import run_streaming
from nifresearch.registry_setup import build_default_registry
from nifresearch.resolution import build_profile
from nifresearch.web.params import build_request_context

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="NIFResearch")


def render_report_fragment(profile, registry_map: dict[str, str]) -> str:
    template = TEMPLATES.env.get_template("_report_body.html")
    return template.render(
        groups=profile.by_type(), results=profile.results, registry=registry_map
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
            html = render_report_fragment(profile, registry_map)
            yield f"event: done\ndata: {json.dumps({'html': html}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 5: Delete the now-unused full report page**

```bash
git rm src/nifresearch/web/templates/report.html
```

- [ ] **Step 6: Run the web tests, then the full suite**

Run: `uv run pytest tests/test_web.py -v` then `uv run pytest -v`
Expected: PASS, output pristine.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: live per-source progress via SSE stream"
```

---

### Task 7: Update README

**Files:**
- Modify: `README.md`

**Interfaces:** none (docs).

- [ ] **Step 1: Update the relevant README lines**

In `README.md`, update the source list and behavior description: replace any mention of the mock/Bar sources with the live set and note the progress UI and strictness dropdown. Add under the run section:
```markdown
The search form has a **source-strictness** dropdown (STRICT default). After you
submit, a **progress page** shows each source's status live (via SSE) and then
renders the report. Live sources: data.gov.il amutot, companies, and the MoH
doctors registry — all official/public. Results are not stored.
```
Ensure the "Adding a source" section still references `nifresearch.sources.base.Source` and `registry_setup.py` (unchanged).

- [ ] **Step 2: Verify the app still launches**

Run: `uv run uvicorn nifresearch.web.app:app --port 8011 &` then `sleep 2 && curl -s localhost:8011/ | grep -q compliance_mode && echo OK`; then stop the server (`kill %1` or the captured PID).
Expected: prints `OK`

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README for v0.2 sources, progress, strictness"
```

---

## Self-Review

**1. Spec coverage:**
- §1 source changes → Task 1 (DoctorsSource), Task 4 (delete mock+Bar, register doctors). ✓
- §2 timeout 25s → Task 2. ✓
- §3 strictness dropdown + `parse_compliance_mode` → Task 3 (helper), Task 5 (dropdown + wiring). ✓
- §4 SSE progress (`run_streaming`, `/research` progress page, `/research/stream`, `_report_body.html`, `research.html`, JSON events) → Task 2 (generator), Task 6 (web + templates). ✓
- §5 privacy note (params in SSE URL) → realized via `stream_url` query string in Task 6; documented in spec. ✓
- §6 testing → each task carries respx/TestClient tests; deletions in Task 4. ✓
- §7 out-of-scope (no no-JS fallback, no job store, simple token search) → respected; `<noscript>` note present. ✓
- §8 version bump → handled at push time per project policy (not a code task).

**2. Placeholder scan:** No TBD/TODO. README task (Task 7) gives concrete copy to add rather than "update docs"; resource IDs and Hebrew field names are concrete and verified.

**3. Type consistency:** `run_streaming(subject, sources, mode, timeout=25.0)` defined in Task 2 and called (3-arg form) in Task 6. `build_request_context(...)` 6-arg signature defined in Task 3, called identically in Tasks 5 and 6. `render_report_fragment(profile, registry_map)` defined and used in Task 6. `DoctorsSource` id `"datagov_doctors"` consistent across Tasks 1, 4, 6. `_report_body.html` context keys (`groups`, `results`, `registry`) match both the `{% include %}` in Task 5 and `render_report_fragment` in Task 6. Doctors fact `detail` keys (`license_number`, `specialty`, `full_name`) consistent between Task 1 code and its test.
