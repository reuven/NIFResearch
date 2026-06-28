# NIFResearch v0.3 Implementation Plan — grey sources + link fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the report's broken/new-tab provenance links, and add 10 grey-market enrichment sources gated behind PERMISSIVE + a configured API key.

**Architecture:** A `GreySource` base class centralizes key-gating (`SKIPPED` when no key), error handling, and grey-flagged fact construction; ten provider subclasses implement only `_fetch`. They join the default registry as `GREY_MARKET` sources, so the existing compliance gate hides them unless PERMISSIVE is chosen. A report banner warns when a grey source actually ran.

**Tech Stack:** Python 3.14, uv, Pydantic v2, FastAPI/SSE, httpx, Jinja2, pytest, pytest-asyncio, respx.

## Global Constraints

- Python `>=3.14`; manage with `uv` (`uv run …`).
- No persistence; results ephemeral.
- Every `Fact` carries provenance (`source_id`, `confidence`, `url`). Grey facts: `confidence=0.25`, `url`=provider site, `detail["caveat"]="grey-market source — verify legal basis before use"`.
- Grey sources are `GREY_MARKET` and **double-gated**: only run under PERMISSIVE compliance mode AND when their API key env var is set; otherwise `SKIPPED`.
- **Breach datasets are excluded** — never integrate leaked registry/voter data.
- All HTTP via the per-source client; **tests mock HTTP with respx; no network, no real keys**.
- Hebrew/RTL templates; external links open in a new tab (`target="_blank" rel="noopener noreferrer"`).
- TDD throughout; run `uv run pytest`.

---

## File Structure

- Modify `src/nifresearch/models.py` — add `FactType.CONTACT`.
- Modify `src/nifresearch/web/templates/_report_body.html` — new-tab links + grey banner.
- Modify `src/nifresearch/sources/datagov_amutot.py`, `datagov_companies.py`, `datagov_doctors.py` — provenance `url` → CKAN API page.
- Create `src/nifresearch/sources/grey/__init__.py`, `src/nifresearch/sources/grey/base.py` — `GreySource`.
- Create 10 provider files under `src/nifresearch/sources/grey/`.
- Modify `src/nifresearch/registry_setup.py` — register the 10 grey sources.
- Modify `src/nifresearch/web/app.py` — `render_report_fragment` gains `grey_ids`; compute and pass.
- Modify `src/nifresearch/web/templates/form.html` — update the dropdown note.
- Create `docs/superpowers/research/grey-sources.md`; modify `README.md`.
- Tests: update the 3 datagov source tests; `tests/test_grey_base.py`; one test file per provider; update `tests/test_registry_setup.py`; add an orchestrator integration test; web banner tests.

---

### Task 1: Report-link fix (new tab + working provenance URLs)

**Files:**
- Modify: `src/nifresearch/web/templates/_report_body.html`
- Modify: `src/nifresearch/sources/datagov_amutot.py`, `datagov_companies.py`, `datagov_doctors.py`
- Test: `tests/test_datagov_amutot.py`, `tests/test_datagov_companies.py`, `tests/test_datagov_doctors.py`

**Interfaces:**
- Produces: the three datagov sources emit facts whose `url` is `https://data.gov.il/api/3/action/package_show?id=<slug>`.

- [ ] **Step 1: Update the three source tests (failing)**

In `tests/test_datagov_amutot.py`, change the url assertion to:
```python
    assert result.facts[0].url == "https://data.gov.il/api/3/action/package_show?id=moj-amutot"
```
In `tests/test_datagov_companies.py`, change the url assertion to:
```python
    assert result.facts[0].url == "https://data.gov.il/api/3/action/package_show?id=ica_companies"
```
In `tests/test_datagov_doctors.py`, change the PROFESSION url assertion to:
```python
    assert prof.url == "https://data.gov.il/api/3/action/package_show?id=database-of-doctors-licenses-moh"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_datagov_amutot.py tests/test_datagov_companies.py tests/test_datagov_doctors.py -q`
Expected: FAIL (old `…/dataset/…` urls)

- [ ] **Step 3: Update the source URLs**

In `src/nifresearch/sources/datagov_amutot.py`, change the fact's `url=` value:
```python
                url="https://data.gov.il/api/3/action/package_show?id=moj-amutot",
```
In `src/nifresearch/sources/datagov_companies.py`, change the fact's `url=` value:
```python
                url="https://data.gov.il/api/3/action/package_show?id=ica_companies",
```
In `src/nifresearch/sources/datagov_doctors.py`, change the `DATASET_URL` constant:
```python
DATASET_URL = "https://data.gov.il/api/3/action/package_show?id=database-of-doctors-licenses-moh"
```

- [ ] **Step 4: Add `target="_blank"` to the report link**

In `src/nifresearch/web/templates/_report_body.html`, replace the link tag inside the facts loop:
```html
{% if f.url and (f.url.startswith('http://') or f.url.startswith('https://')) %}, <a href="{{ f.url }}" target="_blank" rel="noopener noreferrer">קישור</a>{% endif %}
```

- [ ] **Step 5: Run the source tests + full suite**

Run: `uv run pytest tests/test_datagov_amutot.py tests/test_datagov_companies.py tests/test_datagov_doctors.py -q` then `uv run pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "fix: report links open in new tab and use working data.gov.il API URLs"
```

---

### Task 2: FactType.CONTACT + GreySource base class

**Files:**
- Modify: `src/nifresearch/models.py`
- Create: `src/nifresearch/sources/grey/__init__.py` (empty), `src/nifresearch/sources/grey/base.py`
- Test: `tests/test_grey_base.py`

**Interfaces:**
- Consumes: `Source`, models.
- Produces:
  - `FactType.CONTACT = "contact"`.
  - `class GreySource(Source)` with `classification = Classification.GREY_MARKET`, `confidence = 0.25`, class attrs `env_var: str`, `url: str`; `__init__(self, client=None, api_key=None)`; `is_configured() -> bool`; `_grey_fact(self, type, value, **detail) -> Fact`; `async query(...)` (SKIPPED if not configured, NO_MATCH on empty, ERROR on exception, OK otherwise); abstract `async _fetch(self, subject, client) -> list[Fact]`.
  - Module constant `GREY_CAVEAT`.

- [ ] **Step 1: Write the failing test**

`tests/test_grey_base.py`:
```python
import httpx
import pytest

from nifresearch.models import (
    Classification, FactType, InputField, Subject, SourceStatus,
)
from nifresearch.sources.grey.base import GreySource, GREY_CAVEAT


class FakeGrey(GreySource):
    id = "grey_fake"
    name = "Fake grey"
    url = "https://example.com/"
    env_var = "NIFRESEARCH_FAKE_KEY"
    required_inputs = {InputField.NAME}

    async def _fetch(self, subject, client):
        if subject.name_he == "boom":
            raise RuntimeError("kaboom")
        if subject.name_he == "empty":
            return []
        return [self._grey_fact(FactType.CONTACT, "a@b.co", channel="email")]


def test_classification_and_confidence():
    src = FakeGrey(api_key="k")
    assert src.classification == Classification.GREY_MARKET
    assert src.confidence == 0.25


@pytest.mark.asyncio
async def test_not_configured_is_skipped():
    result = await FakeGrey(api_key=None).query(Subject(name_he="x"))
    assert result.status == SourceStatus.SKIPPED
    assert "not configured" in result.error
    assert "NIFRESEARCH_FAKE_KEY" in result.error


@pytest.mark.asyncio
async def test_configured_match_is_ok_with_grey_fact():
    result = await FakeGrey(api_key="k").query(Subject(name_he="ok"))
    assert result.status == SourceStatus.OK
    f = result.facts[0]
    assert f.type == FactType.CONTACT
    assert f.source_id == "grey_fake"
    assert f.confidence == 0.25
    assert f.url == "https://example.com/"
    assert f.detail["caveat"] == GREY_CAVEAT
    assert f.detail["channel"] == "email"


@pytest.mark.asyncio
async def test_empty_is_no_match():
    result = await FakeGrey(api_key="k").query(Subject(name_he="empty"))
    assert result.status == SourceStatus.NO_MATCH


@pytest.mark.asyncio
async def test_exception_is_error():
    result = await FakeGrey(api_key="k").query(Subject(name_he="boom"))
    assert result.status == SourceStatus.ERROR
    assert "kaboom" in result.error
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_grey_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.sources.grey'`

- [ ] **Step 3: Add the enum member**

In `src/nifresearch/models.py`, add to `FactType` (after `LICENSE`):
```python
    CONTACT = "contact"
```

- [ ] **Step 4: Create the package and base class**

Create empty `src/nifresearch/sources/grey/__init__.py`:
```python
```

`src/nifresearch/sources/grey/base.py`:
```python
from __future__ import annotations

import os

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source

GREY_CAVEAT = "grey-market source — verify legal basis before use"


class GreySource(Source):
    classification = Classification.GREY_MARKET
    confidence: float = 0.25
    env_var: str = ""
    url: str = ""

    def __init__(
        self, client: httpx.AsyncClient | None = None, api_key: str | None = None
    ) -> None:
        self._client = client
        self._api_key = api_key if api_key is not None else os.getenv(self.env_var)

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _grey_fact(self, type: FactType, value: str, **detail) -> Fact:
        return Fact(
            type=type,
            value=value,
            source_id=self.id,
            confidence=self.confidence,
            url=self.url,
            detail={**detail, "caveat": GREY_CAVEAT},
        )

    async def query(self, subject: Subject) -> SourceResult:
        if not self.is_configured():
            return SourceResult(
                source_id=self.id, status=SourceStatus.SKIPPED,
                error=f"not configured: set {self.env_var}",
            )
        try:
            if self._client is not None:
                facts = await self._fetch(subject, self._client)
            else:
                async with httpx.AsyncClient() as client:
                    facts = await self._fetch(subject, client)
        except Exception as exc:  # noqa: BLE001 — record any source failure
            return SourceResult(source_id=self.id, status=SourceStatus.ERROR, error=str(exc))
        if not facts:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        raise NotImplementedError
```

- [ ] **Step 5: Run the test + full suite**

Run: `uv run pytest tests/test_grey_base.py -v` then `uv run pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: FactType.CONTACT and GreySource key-gated base class"
```

---

### Task 3: Pipl + People Data Labs sources

**Files:**
- Create: `src/nifresearch/sources/grey/pipl.py`, `src/nifresearch/sources/grey/peopledatalabs.py`
- Test: `tests/test_grey_pipl.py`, `tests/test_grey_pdl.py`

**Interfaces:**
- Consumes: `GreySource`, models.
- Produces: `PiplSource` (id `"grey_pipl"`, env `NIFRESEARCH_PIPL_API_KEY`, inputs name/email/phone) and `PeopleDataLabsSource` (id `"grey_pdl"`, env `NIFRESEARCH_PDL_API_KEY`, inputs name/email/phone).

- [ ] **Step 1: Write the failing tests**

`tests/test_grey_pipl.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.grey.pipl import PiplSource


def test_metadata():
    s = PiplSource(api_key="k")
    assert s.id == "grey_pipl"
    assert s.classification == Classification.GREY_MARKET
    assert InputField.EMAIL in s.required_inputs


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await PiplSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.pipl.com/search/").mock(return_value=httpx.Response(200, json={
        "person": {
            "addresses": [{"display": "Tel Aviv, Israel"}],
            "jobs": [{"display": "CEO at Acme"}],
            "emails": [{"address": "a@b.co"}],
        }
    }))
    async with httpx.AsyncClient() as client:
        r = await PiplSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.ADDRESS, FactType.EMPLOYER, FactType.CONTACT} <= types
    assert all(f.confidence == 0.25 for f in r.facts)
    assert all(f.detail["caveat"] for f in r.facts)
```

`tests/test_grey_pdl.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.peopledatalabs import PeopleDataLabsSource


def test_metadata():
    assert PeopleDataLabsSource(api_key="k").id == "grey_pdl"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await PeopleDataLabsSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.peopledatalabs.com/v5/person/enrich").mock(
        return_value=httpx.Response(200, json={"data": {
            "job_title": "VP Eng", "job_company_name": "Acme",
            "location_name": "Haifa, Israel", "work_email": "a@b.co",
        }})
    )
    async with httpx.AsyncClient() as client:
        r = await PeopleDataLabsSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.EMPLOYER, FactType.ADDRESS, FactType.CONTACT} <= types
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_grey_pipl.py tests/test_grey_pdl.py -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement the sources**

`src/nifresearch/sources/grey/pipl.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class PiplSource(GreySource):
    id = "grey_pipl"
    name = "Pipl (grey-market people search)"
    url = "https://pipl.com/"
    env_var = "NIFRESEARCH_PIPL_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL, InputField.PHONE}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        params: dict[str, str] = {"key": self._api_key}
        if subject.email:
            params["email"] = subject.email
        if subject.phone:
            params["phone"] = subject.phone
        name = subject.name_he or subject.name_en
        if name:
            params["raw_name"] = name
        resp = await client.get("https://api.pipl.com/search/", params=params, timeout=20.0)
        resp.raise_for_status()
        person = (resp.json() or {}).get("person") or {}
        facts: list[Fact] = []
        for addr in person.get("addresses", []):
            if addr.get("display"):
                facts.append(self._grey_fact(FactType.ADDRESS, addr["display"]))
        for job in person.get("jobs", []):
            if job.get("display"):
                facts.append(self._grey_fact(FactType.EMPLOYER, job["display"]))
        for em in person.get("emails", []):
            if em.get("address"):
                facts.append(self._grey_fact(FactType.CONTACT, em["address"], channel="email"))
        return facts
```

`src/nifresearch/sources/grey/peopledatalabs.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class PeopleDataLabsSource(GreySource):
    id = "grey_pdl"
    name = "People Data Labs (grey-market enrichment)"
    url = "https://www.peopledatalabs.com/"
    env_var = "NIFRESEARCH_PDL_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL, InputField.PHONE}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        params: dict[str, str] = {}
        if subject.email:
            params["email"] = subject.email
        if subject.phone:
            params["phone"] = subject.phone
        name = subject.name_he or subject.name_en
        if name:
            params["name"] = name
        resp = await client.get(
            "https://api.peopledatalabs.com/v5/person/enrich",
            params=params, headers={"X-Api-Key": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or {}
        facts: list[Fact] = []
        title, company = data.get("job_title"), data.get("job_company_name")
        if title or company:
            facts.append(self._grey_fact(FactType.EMPLOYER, " @ ".join(p for p in [title, company] if p)))
        if data.get("location_name"):
            facts.append(self._grey_fact(FactType.ADDRESS, data["location_name"]))
        if data.get("work_email"):
            facts.append(self._grey_fact(FactType.CONTACT, data["work_email"], channel="email"))
        return facts
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_grey_pipl.py tests/test_grey_pdl.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: grey sources Pipl and People Data Labs"
```

---

### Task 4: Lusha + Apollo sources

**Files:**
- Create: `src/nifresearch/sources/grey/lusha.py`, `src/nifresearch/sources/grey/apollo.py`
- Test: `tests/test_grey_lusha.py`, `tests/test_grey_apollo.py`

**Interfaces:**
- Produces: `LushaSource` (id `"grey_lusha"`, env `NIFRESEARCH_LUSHA_API_KEY`, inputs name/email) and `ApolloSource` (id `"grey_apollo"`, env `NIFRESEARCH_APOLLO_API_KEY`, inputs name/email).

- [ ] **Step 1: Write the failing tests**

`tests/test_grey_lusha.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.lusha import LushaSource


def test_metadata():
    assert LushaSource(api_key="k").id == "grey_lusha"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await LushaSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.lusha.com/v2/person").mock(return_value=httpx.Response(200, json={
        "data": {
            "jobTitle": "CFO", "companyName": "Acme",
            "emailAddresses": [{"email": "a@b.co"}],
            "phoneNumbers": [{"number": "+972500000000"}],
        }
    }))
    async with httpx.AsyncClient() as client:
        r = await LushaSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.ROLE, FactType.EMPLOYER, FactType.CONTACT} <= types
```

`tests/test_grey_apollo.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.apollo import ApolloSource


def test_metadata():
    assert ApolloSource(api_key="k").id == "grey_apollo"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await ApolloSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.post("https://api.apollo.io/v1/people/match").mock(return_value=httpx.Response(200, json={
        "person": {
            "title": "Director", "organization": {"name": "Acme"},
            "email": "a@b.co", "phone_numbers": [{"raw_number": "+972500000000"}],
        }
    }))
    async with httpx.AsyncClient() as client:
        r = await ApolloSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.ROLE, FactType.EMPLOYER, FactType.CONTACT} <= types
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_grey_lusha.py tests/test_grey_apollo.py -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement the sources**

`src/nifresearch/sources/grey/lusha.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class LushaSource(GreySource):
    id = "grey_lusha"
    name = "Lusha (grey-market B2B enrichment)"
    url = "https://www.lusha.com/"
    env_var = "NIFRESEARCH_LUSHA_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        params: dict[str, str] = {}
        if subject.email:
            params["email"] = subject.email
        name = subject.name_he or subject.name_en
        if name:
            params["name"] = name
        resp = await client.get(
            "https://api.lusha.com/v2/person",
            params=params, headers={"api_key": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or {}
        facts: list[Fact] = []
        if data.get("jobTitle"):
            facts.append(self._grey_fact(FactType.ROLE, data["jobTitle"]))
        if data.get("companyName"):
            facts.append(self._grey_fact(FactType.EMPLOYER, data["companyName"]))
        for em in data.get("emailAddresses", []):
            if em.get("email"):
                facts.append(self._grey_fact(FactType.CONTACT, em["email"], channel="email"))
        for ph in data.get("phoneNumbers", []):
            if ph.get("number"):
                facts.append(self._grey_fact(FactType.CONTACT, ph["number"], channel="phone"))
        return facts
```

`src/nifresearch/sources/grey/apollo.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class ApolloSource(GreySource):
    id = "grey_apollo"
    name = "Apollo.io (grey-market enrichment)"
    url = "https://www.apollo.io/"
    env_var = "NIFRESEARCH_APOLLO_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        payload: dict[str, str] = {}
        if subject.email:
            payload["email"] = subject.email
        name = subject.name_he or subject.name_en
        if name:
            payload["name"] = name
        resp = await client.post(
            "https://api.apollo.io/v1/people/match",
            json=payload, headers={"X-Api-Key": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        person = (resp.json() or {}).get("person") or {}
        facts: list[Fact] = []
        if person.get("title"):
            facts.append(self._grey_fact(FactType.ROLE, person["title"]))
        org = person.get("organization") or {}
        if org.get("name"):
            facts.append(self._grey_fact(FactType.EMPLOYER, org["name"]))
        if person.get("email"):
            facts.append(self._grey_fact(FactType.CONTACT, person["email"], channel="email"))
        for ph in person.get("phone_numbers", []):
            if ph.get("raw_number"):
                facts.append(self._grey_fact(FactType.CONTACT, ph["raw_number"], channel="phone"))
        return facts
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_grey_lusha.py tests/test_grey_apollo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: grey sources Lusha and Apollo"
```

---

### Task 5: Hunter.io + ContactOut sources

**Files:**
- Create: `src/nifresearch/sources/grey/hunter.py`, `src/nifresearch/sources/grey/contactout.py`
- Test: `tests/test_grey_hunter.py`, `tests/test_grey_contactout.py`

**Interfaces:**
- Produces: `HunterSource` (id `"grey_hunter"`, env `NIFRESEARCH_HUNTER_API_KEY`, inputs email) and `ContactOutSource` (id `"grey_contactout"`, env `NIFRESEARCH_CONTACTOUT_API_KEY`, inputs email).

- [ ] **Step 1: Write the failing tests**

`tests/test_grey_hunter.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus
from nifresearch.sources.grey.hunter import HunterSource


def test_metadata():
    s = HunterSource(api_key="k")
    assert s.id == "grey_hunter"
    assert s.required_inputs == {InputField.EMAIL}


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await HunterSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_contact():
    respx.get("https://api.hunter.io/v2/email-verifier").mock(return_value=httpx.Response(200, json={
        "data": {"status": "valid", "score": 96, "email": "a@b.co"}
    }))
    async with httpx.AsyncClient() as client:
        r = await HunterSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    f = r.facts[0]
    assert f.type == FactType.CONTACT
    assert f.detail["status"] == "valid"
```

`tests/test_grey_contactout.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.contactout import ContactOutSource


def test_metadata():
    assert ContactOutSource(api_key="k").id == "grey_contactout"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await ContactOutSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.contactout.com/v1/people/enrich").mock(return_value=httpx.Response(200, json={
        "profile": {
            "full_name": "David Cohen",
            "emails": ["a@b.co"], "phones": ["+972500000000"],
            "company": {"name": "Acme"},
        }
    }))
    async with httpx.AsyncClient() as client:
        r = await ContactOutSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.CONTACT, FactType.EMPLOYER} <= types
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_grey_hunter.py tests/test_grey_contactout.py -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement the sources**

`src/nifresearch/sources/grey/hunter.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class HunterSource(GreySource):
    id = "grey_hunter"
    name = "Hunter.io (grey-market email verification)"
    url = "https://hunter.io/"
    env_var = "NIFRESEARCH_HUNTER_API_KEY"
    required_inputs = {InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.email:
            return []
        resp = await client.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": subject.email},
            headers={"Authorization": f"Bearer {self._api_key}"}, timeout=20.0,
        )
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or {}
        if not data.get("email"):
            return []
        return [self._grey_fact(
            FactType.CONTACT, data["email"],
            channel="email", status=data.get("status", ""), score=data.get("score"),
        )]
```

`src/nifresearch/sources/grey/contactout.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class ContactOutSource(GreySource):
    id = "grey_contactout"
    name = "ContactOut (grey-market enrichment)"
    url = "https://contactout.com/"
    env_var = "NIFRESEARCH_CONTACTOUT_API_KEY"
    required_inputs = {InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.email:
            return []
        resp = await client.get(
            "https://api.contactout.com/v1/people/enrich",
            params={"email": subject.email},
            headers={"authorization": f"Basic {self._api_key}"}, timeout=20.0,
        )
        resp.raise_for_status()
        profile = (resp.json() or {}).get("profile") or {}
        facts: list[Fact] = []
        for em in profile.get("emails", []):
            facts.append(self._grey_fact(FactType.CONTACT, em, channel="email"))
        for ph in profile.get("phones", []):
            facts.append(self._grey_fact(FactType.CONTACT, ph, channel="phone"))
        company = profile.get("company") or {}
        if company.get("name"):
            facts.append(self._grey_fact(FactType.EMPLOYER, company["name"]))
        return facts
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_grey_hunter.py tests/test_grey_contactout.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: grey sources Hunter.io and ContactOut"
```

---

### Task 6: RocketReach + Clearbit sources

**Files:**
- Create: `src/nifresearch/sources/grey/rocketreach.py`, `src/nifresearch/sources/grey/clearbit.py`
- Test: `tests/test_grey_rocketreach.py`, `tests/test_grey_clearbit.py`

**Interfaces:**
- Produces: `RocketReachSource` (id `"grey_rocketreach"`, env `NIFRESEARCH_ROCKETREACH_API_KEY`, inputs name/email) and `ClearbitSource` (id `"grey_clearbit"`, env `NIFRESEARCH_CLEARBIT_API_KEY`, inputs email).

- [ ] **Step 1: Write the failing tests**

`tests/test_grey_rocketreach.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.rocketreach import RocketReachSource


def test_metadata():
    assert RocketReachSource(api_key="k").id == "grey_rocketreach"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await RocketReachSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.rocketreach.co/v2/api/lookupProfile").mock(
        return_value=httpx.Response(200, json={
            "emails": [{"email": "a@b.co"}], "phones": [{"number": "+972500000000"}],
            "current_employer": "Acme", "current_title": "Partner",
        })
    )
    async with httpx.AsyncClient() as client:
        r = await RocketReachSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.CONTACT, FactType.EMPLOYER, FactType.ROLE} <= types
```

`tests/test_grey_clearbit.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.clearbit import ClearbitSource


def test_metadata():
    assert ClearbitSource(api_key="k").id == "grey_clearbit"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await ClearbitSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://person.clearbit.com/v2/people/find").mock(
        return_value=httpx.Response(200, json={
            "email": "a@b.co",
            "employment": {"name": "Acme", "title": "Chair"},
        })
    )
    async with httpx.AsyncClient() as client:
        r = await ClearbitSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.CONTACT, FactType.EMPLOYER} <= types
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_grey_rocketreach.py tests/test_grey_clearbit.py -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement the sources**

`src/nifresearch/sources/grey/rocketreach.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class RocketReachSource(GreySource):
    id = "grey_rocketreach"
    name = "RocketReach (grey-market enrichment)"
    url = "https://rocketreach.co/"
    env_var = "NIFRESEARCH_ROCKETREACH_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        params: dict[str, str] = {}
        if subject.email:
            params["email"] = subject.email
        name = subject.name_he or subject.name_en
        if name:
            params["name"] = name
        resp = await client.get(
            "https://api.rocketreach.co/v2/api/lookupProfile",
            params=params, headers={"Api-Key": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        facts: list[Fact] = []
        for em in data.get("emails", []):
            if em.get("email"):
                facts.append(self._grey_fact(FactType.CONTACT, em["email"], channel="email"))
        for ph in data.get("phones", []):
            if ph.get("number"):
                facts.append(self._grey_fact(FactType.CONTACT, ph["number"], channel="phone"))
        if data.get("current_employer"):
            facts.append(self._grey_fact(FactType.EMPLOYER, data["current_employer"]))
        if data.get("current_title"):
            facts.append(self._grey_fact(FactType.ROLE, data["current_title"]))
        return facts
```

`src/nifresearch/sources/grey/clearbit.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class ClearbitSource(GreySource):
    id = "grey_clearbit"
    name = "Clearbit/Breeze (grey-market enrichment)"
    url = "https://clearbit.com/"
    env_var = "NIFRESEARCH_CLEARBIT_API_KEY"
    required_inputs = {InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.email:
            return []
        resp = await client.get(
            "https://person.clearbit.com/v2/people/find",
            params={"email": subject.email},
            headers={"Authorization": f"Bearer {self._api_key}"}, timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        facts: list[Fact] = []
        employment = data.get("employment") or {}
        if employment.get("name"):
            facts.append(self._grey_fact(FactType.EMPLOYER, employment["name"]))
        if employment.get("title"):
            facts.append(self._grey_fact(FactType.ROLE, employment["title"]))
        if data.get("email"):
            facts.append(self._grey_fact(FactType.CONTACT, data["email"], channel="email"))
        return facts
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_grey_rocketreach.py tests/test_grey_clearbit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: grey sources RocketReach and Clearbit"
```

---

### Task 7: NumVerify + Twilio Lookup sources

**Files:**
- Create: `src/nifresearch/sources/grey/numverify.py`, `src/nifresearch/sources/grey/twilio_lookup.py`
- Test: `tests/test_grey_numverify.py`, `tests/test_grey_twilio.py`

**Interfaces:**
- Produces: `NumVerifySource` (id `"grey_numverify"`, env `NIFRESEARCH_NUMVERIFY_KEY`, inputs phone) and `TwilioLookupSource` (id `"grey_twilio"`, inputs phone, two-credential config via `NIFRESEARCH_TWILIO_SID`+`NIFRESEARCH_TWILIO_TOKEN`, with an `auth=(sid, token)` constructor override for tests).

- [ ] **Step 1: Write the failing tests**

`tests/test_grey_numverify.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.numverify import NumVerifySource


def test_metadata():
    assert NumVerifySource(api_key="k").id == "grey_numverify"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await NumVerifySource(api_key=None).query(Subject(phone="+972500000000"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://apilayer.net/api/validate").mock(return_value=httpx.Response(200, json={
        "valid": True, "carrier": "Pelephone", "line_type": "mobile",
        "location": "Israel", "country_name": "Israel",
    }))
    async with httpx.AsyncClient() as client:
        r = await NumVerifySource(client=client, api_key="k").query(Subject(phone="+972500000000"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert FactType.CONTACT in types
```

`tests/test_grey_twilio.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus, Classification
from nifresearch.sources.grey.twilio_lookup import TwilioLookupSource


def test_metadata_and_classification():
    s = TwilioLookupSource(auth=("sid", "tok"))
    assert s.id == "grey_twilio"
    assert s.classification == Classification.GREY_MARKET


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await TwilioLookupSource(auth=("", "")).query(Subject(phone="+972500000000"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_caller_name():
    respx.get("https://lookups.twilio.com/v2/PhoneNumbers/+972500000000").mock(
        return_value=httpx.Response(200, json={"caller_name": {"caller_name": "David Cohen"}})
    )
    async with httpx.AsyncClient() as client:
        r = await TwilioLookupSource(client=client, auth=("sid", "tok")).query(
            Subject(phone="+972500000000")
        )
    assert r.status == SourceStatus.OK
    assert r.facts[0].type == FactType.CONTACT
    assert r.facts[0].value == "David Cohen"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_grey_numverify.py tests/test_grey_twilio.py -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement the sources**

`src/nifresearch/sources/grey/numverify.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class NumVerifySource(GreySource):
    id = "grey_numverify"
    name = "NumVerify (grey-market phone validation)"
    url = "https://numverify.com/"
    env_var = "NIFRESEARCH_NUMVERIFY_KEY"
    required_inputs = {InputField.PHONE}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.phone:
            return []
        resp = await client.get(
            "https://apilayer.net/api/validate",
            params={"number": subject.phone},
            headers={"apikey": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        if not data.get("valid"):
            return []
        facts: list[Fact] = []
        carrier = data.get("carrier")
        line = data.get("line_type")
        if carrier or line:
            facts.append(self._grey_fact(
                FactType.CONTACT, " / ".join(p for p in [carrier, line] if p),
                channel="phone",
            ))
        loc = data.get("location") or data.get("country_name")
        if loc:
            facts.append(self._grey_fact(FactType.ADDRESS, loc))
        return facts
```

`src/nifresearch/sources/grey/twilio_lookup.py`:
```python
from __future__ import annotations

import os

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class TwilioLookupSource(GreySource):
    id = "grey_twilio"
    name = "Twilio Lookup (grey-market caller ID)"
    url = "https://www.twilio.com/lookup"
    env_var = "NIFRESEARCH_TWILIO_SID"  # informational; auth uses two vars
    required_inputs = {InputField.PHONE}

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        auth: tuple[str, str] | None = None,
    ) -> None:
        self._client = client
        if auth is not None:
            self._sid, self._token = auth
        else:
            self._sid = os.getenv("NIFRESEARCH_TWILIO_SID") or ""
            self._token = os.getenv("NIFRESEARCH_TWILIO_TOKEN") or ""

    def is_configured(self) -> bool:
        return bool(self._sid and self._token)

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.phone:
            return []
        resp = await client.get(
            f"https://lookups.twilio.com/v2/PhoneNumbers/{subject.phone}",
            params={"Fields": "caller_name"},
            auth=(self._sid, self._token), timeout=20.0,
        )
        resp.raise_for_status()
        caller = (resp.json() or {}).get("caller_name") or {}
        name = caller.get("caller_name")
        return [self._grey_fact(FactType.CONTACT, name, channel="caller_id")] if name else []
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_grey_numverify.py tests/test_grey_twilio.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: grey sources NumVerify and Twilio Lookup"
```

---

### Task 8: Register grey sources + orchestrator gating test

**Files:**
- Modify: `src/nifresearch/registry_setup.py`
- Modify: `tests/test_registry_setup.py`
- Test: `tests/test_orchestrator.py` (append)

**Interfaces:**
- Produces: `build_default_registry` returns 13 sources: `datagov_amutot`, `datagov_companies`, `datagov_doctors`, `grey_pipl`, `grey_lusha`, `grey_hunter`, `grey_numverify`, `grey_twilio`, `grey_apollo`, `grey_rocketreach`, `grey_contactout`, `grey_clearbit`, `grey_pdl`.

- [ ] **Step 1: Update the registry test (failing)**

Replace `tests/test_registry_setup.py`:
```python
from nifresearch.registry_setup import build_default_registry


def test_default_registry_contains_expected_sources():
    reg = build_default_registry()
    ids = [s.id for s in reg.all()]
    assert ids == [
        "datagov_amutot", "datagov_companies", "datagov_doctors",
        "grey_pipl", "grey_lusha", "grey_hunter", "grey_numverify", "grey_twilio",
        "grey_apollo", "grey_rocketreach", "grey_contactout", "grey_clearbit", "grey_pdl",
    ]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_registry_setup.py -v`
Expected: FAIL

- [ ] **Step 3: Update the registry**

Replace `src/nifresearch/registry_setup.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.sources.base import SourceRegistry
from nifresearch.sources.datagov_amutot import AmutotSource
from nifresearch.sources.datagov_companies import CompaniesSource
from nifresearch.sources.datagov_doctors import DoctorsSource
from nifresearch.sources.grey.apollo import ApolloSource
from nifresearch.sources.grey.clearbit import ClearbitSource
from nifresearch.sources.grey.contactout import ContactOutSource
from nifresearch.sources.grey.hunter import HunterSource
from nifresearch.sources.grey.lusha import LushaSource
from nifresearch.sources.grey.numverify import NumVerifySource
from nifresearch.sources.grey.peopledatalabs import PeopleDataLabsSource
from nifresearch.sources.grey.pipl import PiplSource
from nifresearch.sources.grey.rocketreach import RocketReachSource
from nifresearch.sources.grey.twilio_lookup import TwilioLookupSource


def build_default_registry(client: httpx.AsyncClient | None = None) -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(AmutotSource(client))
    registry.register(CompaniesSource(client))
    registry.register(DoctorsSource(client))
    registry.register(PiplSource(client))
    registry.register(LushaSource(client))
    registry.register(HunterSource(client))
    registry.register(NumVerifySource(client))
    registry.register(TwilioLookupSource(client))
    registry.register(ApolloSource(client))
    registry.register(RocketReachSource(client))
    registry.register(ContactOutSource(client))
    registry.register(ClearbitSource(client))
    registry.register(PeopleDataLabsSource(client))
    return registry
```

- [ ] **Step 4: Add the orchestrator gating test (append to `tests/test_orchestrator.py`)**

Add imports at top if missing: `import httpx`, `import respx`, `from nifresearch.sources.grey.pipl import PiplSource`. Append:
```python
@pytest.mark.asyncio
async def test_grey_source_blocked_under_strict():
    src = PiplSource(api_key="k")
    results = await run(Subject(email="a@b.co"), [src], ComplianceMode.STRICT)
    assert results[0].status == SourceStatus.SKIPPED
    assert "compliance" in results[0].error


@pytest.mark.asyncio
@respx.mock
async def test_grey_source_runs_under_permissive():
    respx.get("https://api.pipl.com/search/").mock(return_value=httpx.Response(200, json={
        "person": {"emails": [{"address": "a@b.co"}]}
    }))
    async with httpx.AsyncClient() as client:
        src = PiplSource(client=client, api_key="k")
        results = await run(Subject(email="a@b.co"), [src], ComplianceMode.PERMISSIVE)
    assert results[0].status == SourceStatus.OK
```

- [ ] **Step 5: Run the tests + full suite**

Run: `uv run pytest tests/test_registry_setup.py tests/test_orchestrator.py -v` then `uv run pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: register 10 grey sources; orchestrator gating tests"
```

---

### Task 9: Report grey banner + form note

**Files:**
- Modify: `src/nifresearch/web/app.py`
- Modify: `src/nifresearch/web/templates/_report_body.html`
- Modify: `src/nifresearch/web/templates/form.html`
- Test: `tests/test_web.py` (append)

**Interfaces:**
- Consumes: `Classification`, `SourceStatus`, `build_default_registry`, `run_streaming`, `build_profile`.
- Produces: `render_report_fragment(profile, registry_map, grey_ids: set[str]) -> str` (new third param); template shows a banner when a grey source ran.

- [ ] **Step 1: Write the failing tests (append to `tests/test_web.py`)**

```python
from urllib.parse import quote as _quote


@respx.mock
def test_grey_banner_absent_under_strict():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    client = TestClient(app)
    resp = client.get("/research/stream?name_he=" + _quote("דוד"))
    assert "grey-market" not in resp.text


@respx.mock
def test_grey_banner_present_when_grey_ran(monkeypatch):
    monkeypatch.setenv("NIFRESEARCH_PIPL_API_KEY", "k")
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    respx.get("https://api.pipl.com/search/").mock(return_value=httpx.Response(200, json={
        "person": {"emails": [{"address": "a@b.co"}]}
    }))
    client = TestClient(app)
    resp = client.get(
        "/research/stream?compliance_mode=permissive&email=" + _quote("a@b.co")
    )
    assert "grey-market" in resp.text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_web.py::test_grey_banner_present_when_grey_ran -v`
Expected: FAIL (no banner)

- [ ] **Step 3: Update `render_report_fragment` and the stream handler in `app.py`**

In `src/nifresearch/web/app.py`, add imports: `from nifresearch.models import Classification, SourceStatus`. Replace `render_report_fragment`:
```python
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
```
In `research_stream`'s `event_stream`, where `sources`/`registry_map` are built, also compute `grey_ids` and pass it to the fragment renderer:
```python
            registry_map = {s.id: s.name for s in sources}
            grey_ids = {s.id for s in sources if s.classification == Classification.GREY_MARKET}
```
and change the `done` render call:
```python
            html = render_report_fragment(profile, registry_map, grey_ids)
```

- [ ] **Step 4: Add the banner to `_report_body.html`**

At the very top of `src/nifresearch/web/templates/_report_body.html`, add:
```html
{% if grey_ran %}
  <div class="warn" style="background:#f8d7da;border-color:#f5c2c7;">
    ⚠️ מקורות אפורים (grey-market) נשאלו — יש לוודא בסיס חוקי לפני הסתמכות על המידע.
  </div>
{% endif %}
```

- [ ] **Step 5: Update the form note**

In `src/nifresearch/web/templates/form.html`, replace the note paragraph under the dropdown:
```html
    <p class="note">מקורות אפורים (grey-market) פעילים רק במצב permissive ורק כאשר הוגדר מפתח API לכל מקור. כברירת מחדל הם חסומים.</p>
```

- [ ] **Step 6: Run the web tests + full suite**

Run: `uv run pytest tests/test_web.py -v` then `uv run pytest -q`
Expected: PASS, pristine

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: grey-market report banner and updated form note"
```

---

### Task 10: Docs — grey-sources catalog + README

**Files:**
- Create: `docs/superpowers/research/grey-sources.md`
- Modify: `README.md`

**Interfaces:** none (docs).

- [ ] **Step 1: Write the grey-sources catalog**

Create `docs/superpowers/research/grey-sources.md`:
```markdown
# Grey-market sources — operator reference

> **⚠️ DO NOT ENABLE WITHOUT LEGAL SIGN-OFF.** These are commercial data-broker /
> enrichment APIs. They are classified `grey_market` and are **double-gated**:
> they run only under the **PERMISSIVE** compliance mode AND only when their API
> key environment variable is set. By default they are blocked. Confirm a lawful
> basis under Israel's Privacy Protection Law (incl. Amendment 13) before enabling
> any of them for real data.
>
> **Breach-sourced datasets (leaked population/voter registries) are excluded by
> policy and are never integrated.**

| Source | id | Input(s) | Env key(s) | Returns |
|--------|----|----------|------------|---------|
| Pipl | grey_pipl | name/email/phone | NIFRESEARCH_PIPL_API_KEY | address, employer, contact |
| Lusha | grey_lusha | name/email | NIFRESEARCH_LUSHA_API_KEY | role, employer, contact |
| Hunter.io | grey_hunter | email | NIFRESEARCH_HUNTER_API_KEY | email verification |
| NumVerify | grey_numverify | phone | NIFRESEARCH_NUMVERIFY_KEY | carrier/line, location |
| Twilio Lookup | grey_twilio | phone | NIFRESEARCH_TWILIO_SID + NIFRESEARCH_TWILIO_TOKEN | caller name |
| Apollo.io | grey_apollo | name/email | NIFRESEARCH_APOLLO_API_KEY | role, employer, contact |
| RocketReach | grey_rocketreach | name/email | NIFRESEARCH_ROCKETREACH_API_KEY | contact, employer, role |
| ContactOut | grey_contactout | email | NIFRESEARCH_CONTACTOUT_API_KEY | contact, employer |
| Clearbit/Breeze | grey_clearbit | email | NIFRESEARCH_CLEARBIT_API_KEY | employer, contact |
| People Data Labs | grey_pdl | name/email/phone | NIFRESEARCH_PDL_API_KEY | employer, address, contact |

Each grey fact is tagged `confidence=0.25`, carries the provider URL, and includes
`detail["caveat"] = "grey-market source — verify legal basis before use"`. The
report shows a warning banner whenever any grey source actually ran.

Exact endpoints/fields are representative and must be confirmed against current
provider documentation before relying on results.
```

- [ ] **Step 2: Add a README section**

In `README.md`, add after the Privacy note:
```markdown
## Grey-market sources (disabled by default)

Ten commercial data-broker / enrichment sources are available but **double-gated**:
they run only under the **PERMISSIVE** strictness setting AND only when their API
key environment variable is set (e.g. `NIFRESEARCH_PIPL_API_KEY`). With no keys,
they report "not configured" and do nothing. See
`docs/superpowers/research/grey-sources.md` for the full list and the legal
caveat — **do not enable for real data without legal sign-off.** Breach-sourced
datasets are never integrated.
```

- [ ] **Step 3: Verify the app still launches**

Run: `uv run uvicorn nifresearch.web.app:app --port 8012 &` then `sleep 2 && curl -s localhost:8012/ | grep -q compliance_mode && echo OK`; then stop the server (kill the captured PID).
Expected: prints `OK`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: grey-sources catalog and README section"
```

---

## Self-Review

**1. Spec coverage:** §1 link fix → Task 1. §2 gating (no change) → relied upon; verified by Task 8 orchestrator tests. §3 FactType.CONTACT → Task 2. §4 GreySource base → Task 2. §5 ten providers → Tasks 3–7. §6 registry (13) → Task 8. §7 banner + form note → Task 9. §8 testing → per-task respx tests + base + orchestrator + web banner. §9 docs → Task 10. §10 out-of-scope respected (no real calls/keys, no breach data, no caching). §11 version → push-time.

**2. Placeholder scan:** No TBD/TODO. Provider endpoints are concrete (representative, flagged in spec/docs). All code blocks complete.

**3. Type consistency:** `GreySource.__init__(client, api_key)`, `is_configured`, `_grey_fact(type, value, **detail)`, `_fetch(subject, client)` defined in Task 2 and used identically in Tasks 3–7. `TwilioLookupSource(client, auth)` override matches its test usage. `render_report_fragment(profile, registry_map, grey_ids)` (Task 9) — note this changes the v0.2 two-arg signature; the only caller is `research_stream`, updated in the same task. Registry ids in Task 8 match each provider's `id`. `FactType.CONTACT` (Task 2) used by all providers. Grey `confidence=0.25` consistent (base default) across providers and asserted in tests.
```
