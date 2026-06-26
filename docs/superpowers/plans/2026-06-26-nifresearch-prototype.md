# NIFResearch Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app that takes any subset of {name, email, phone, Israeli ID}, fans out to pluggable Israeli data sources, merges results into a provenance-tagged profile, and renders an RTL HTML report.

**Architecture:** A FastAPI web layer calls an async orchestrator that input-gates and compliance-gates a registry of `Source` plugins, runs the eligible ones concurrently, and passes their `SourceResult`s to a resolution layer that groups facts into a `Profile`. Each plugin declares its required inputs and legal classification, so the orchestrator can skip sources lacking inputs or blocked by the active compliance mode. Results are session-ephemeral — nothing is persisted.

**Tech Stack:** Python 3.14, uv, Pydantic v2, FastAPI, httpx, Jinja2, pytest, pytest-asyncio, respx.

## Global Constraints

- Python `>=3.14`; manage with `uv` (`uv run …`, `uv add …`).
- No persistence: results live only for the request. No database, no writing results to disk.
- Every `Fact` carries provenance: `source_id`, `confidence`, and (where available) `url`.
- Default compliance mode is **STRICT** (`official_public` sources only). `licensed` requires opt-in; `grey_market` is never enabled in this prototype.
- Live sources used in this slice are all free, `official_public`, API/dataset-backed: `data.gov.il` CKAN (amutot + companies) and `odata.org.il` CKAN (Israel Bar lawyers).
- Hebrew/RTL: source values are Hebrew; the report template must set `dir="rtl"` and `lang="he"` on the body.
- All source HTTP goes through a shared async CKAN client; tests mock HTTP with `respx` (never hit the network).
- TDD throughout: failing test → minimal code → passing test → commit.

---

## File Structure

- `src/nifresearch/__init__.py` — package marker.
- `src/nifresearch/models.py` — enums + Pydantic domain models.
- `src/nifresearch/validation.py` — Israeli-ID checksum + input normalization.
- `src/nifresearch/sources/__init__.py` — package marker.
- `src/nifresearch/sources/base.py` — `Source` ABC + `SourceRegistry`.
- `src/nifresearch/sources/mock.py` — deterministic mock source for dev/tests.
- `src/nifresearch/sources/ckan.py` — shared async CKAN client.
- `src/nifresearch/sources/datagov_amutot.py` — amutot (non-profit) source.
- `src/nifresearch/sources/datagov_companies.py` — companies source.
- `src/nifresearch/sources/bar_lawyers.py` — Israel Bar lawyers source.
- `src/nifresearch/compliance.py` — classification gating.
- `src/nifresearch/orchestrator.py` — concurrent fan-out.
- `src/nifresearch/resolution.py` — merge results into a `Profile`.
- `src/nifresearch/registry_setup.py` — build the default registry of sources.
- `src/nifresearch/web/__init__.py` — package marker.
- `src/nifresearch/web/app.py` — FastAPI app + routes.
- `src/nifresearch/web/templates/form.html`, `report.html` — Jinja2 templates.
- `tests/…` — one test module per source file above.

---

### Task 1: Project setup, dependencies, and layout

**Files:**
- Modify: `pyproject.toml`
- Create: `src/nifresearch/__init__.py`
- Delete: `main.py` (boilerplate)
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an importable `nifresearch` package and a working `uv run pytest`.

- [ ] **Step 1: Add dependencies**

Run:
```bash
uv add fastapi "pydantic>=2" httpx jinja2 "uvicorn[standard]"
uv add --dev pytest pytest-asyncio respx httpx
```

- [ ] **Step 2: Configure package layout, pytest, and asyncio mode**

Replace `pyproject.toml`'s `[project]` block contents as needed and append:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/nifresearch"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Ensure the build backend exists in `pyproject.toml` (uv adds `[build-system]` with hatchling; if absent, add):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Create the package and remove boilerplate**

```bash
mkdir -p src/nifresearch tests
printf '"""NIFResearch — Israeli prospect-research prototype."""\n' > src/nifresearch/__init__.py
rm -f main.py
```

- [ ] **Step 4: Write the smoke test**

`tests/test_smoke.py`:
```python
import nifresearch


def test_package_imports():
    assert nifresearch.__doc__
```

- [ ] **Step 5: Run it and verify it passes**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/nifresearch/__init__.py tests/test_smoke.py
git rm --cached main.py 2>/dev/null; git add -A
git commit -m "chore: project setup, deps, src layout"
```

---

### Task 2: Domain models and enums

**Files:**
- Create: `src/nifresearch/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class Classification(str, Enum)`: `OFFICIAL_PUBLIC="official_public"`, `LICENSED="licensed"`, `GREY_MARKET="grey_market"`.
  - `class ComplianceMode(str, Enum)`: `STRICT="strict"`, `STANDARD="standard"`, `PERMISSIVE="permissive"`.
  - `class InputField(str, Enum)`: `NAME="name"`, `EMAIL="email"`, `PHONE="phone"`, `ID_NUMBER="id_number"`.
  - `class FactType(str, Enum)`: `ADDRESS`, `EMPLOYER`, `ROLE`, `BOARD_MEMBERSHIP`, `PROFESSION`, `LICENSE`, `ORG_AFFILIATION`, `DONATION`, `INCOME_ESTIMATE`, `OTHER` (values = lowercase names).
  - `class SourceStatus(str, Enum)`: `OK="ok"`, `NO_MATCH="no_match"`, `ERROR="error"`, `SKIPPED="skipped"`.
  - `class Subject(BaseModel)`: fields `name_he: str|None=None`, `name_en: str|None=None`, `email: str|None=None`, `phone: str|None=None`, `id_number: str|None=None`; method `available_inputs(self) -> set[InputField]`.
  - `class Fact(BaseModel)`: `type: FactType`, `value: str`, `source_id: str`, `confidence: float=0.5`, `url: str|None=None`, `retrieved_at: str|None=None`, `detail: dict=Field(default_factory=dict)`.
  - `class SourceResult(BaseModel)`: `source_id: str`, `status: SourceStatus`, `facts: list[Fact]=Field(default_factory=list)`, `latency_ms: float|None=None`, `error: str|None=None`.
  - `class Profile(BaseModel)`: `subject: Subject`, `facts: list[Fact]=...`, `results: list[SourceResult]=...`; method `by_type(self) -> dict[FactType, list[Fact]]`.

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from nifresearch.models import (
    Classification, ComplianceMode, InputField, FactType, SourceStatus,
    Subject, Fact, SourceResult, Profile,
)


def test_enum_values():
    assert Classification.OFFICIAL_PUBLIC.value == "official_public"
    assert ComplianceMode.STRICT.value == "strict"
    assert InputField.ID_NUMBER.value == "id_number"
    assert FactType.BOARD_MEMBERSHIP.value == "board_membership"
    assert SourceStatus.OK.value == "ok"


def test_subject_available_inputs():
    s = Subject(name_he="דוד כהן", email="d@example.com")
    assert s.available_inputs() == {InputField.NAME, InputField.EMAIL}
    assert Subject(name_en="David Cohen").available_inputs() == {InputField.NAME}
    assert Subject().available_inputs() == set()


def test_profile_groups_facts_by_type():
    f1 = Fact(type=FactType.ROLE, value="יו\"ר", source_id="x")
    f2 = Fact(type=FactType.ROLE, value="חבר ועד", source_id="x")
    f3 = Fact(type=FactType.PROFESSION, value="עו\"ד", source_id="y")
    p = Profile(subject=Subject(), facts=[f1, f2, f3], results=[])
    grouped = p.by_type()
    assert grouped[FactType.ROLE] == [f1, f2]
    assert grouped[FactType.PROFESSION] == [f3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.models'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/models.py`:
```python
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Classification(str, Enum):
    OFFICIAL_PUBLIC = "official_public"
    LICENSED = "licensed"
    GREY_MARKET = "grey_market"


class ComplianceMode(str, Enum):
    STRICT = "strict"
    STANDARD = "standard"
    PERMISSIVE = "permissive"


class InputField(str, Enum):
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    ID_NUMBER = "id_number"


class FactType(str, Enum):
    ADDRESS = "address"
    EMPLOYER = "employer"
    ROLE = "role"
    BOARD_MEMBERSHIP = "board_membership"
    PROFESSION = "profession"
    LICENSE = "license"
    ORG_AFFILIATION = "org_affiliation"
    DONATION = "donation"
    INCOME_ESTIMATE = "income_estimate"
    OTHER = "other"


class SourceStatus(str, Enum):
    OK = "ok"
    NO_MATCH = "no_match"
    ERROR = "error"
    SKIPPED = "skipped"


class Subject(BaseModel):
    name_he: str | None = None
    name_en: str | None = None
    email: str | None = None
    phone: str | None = None
    id_number: str | None = None

    def available_inputs(self) -> set[InputField]:
        present: set[InputField] = set()
        if self.name_he or self.name_en:
            present.add(InputField.NAME)
        if self.email:
            present.add(InputField.EMAIL)
        if self.phone:
            present.add(InputField.PHONE)
        if self.id_number:
            present.add(InputField.ID_NUMBER)
        return present


class Fact(BaseModel):
    type: FactType
    value: str
    source_id: str
    confidence: float = 0.5
    url: str | None = None
    retrieved_at: str | None = None
    detail: dict = Field(default_factory=dict)


class SourceResult(BaseModel):
    source_id: str
    status: SourceStatus
    facts: list[Fact] = Field(default_factory=list)
    latency_ms: float | None = None
    error: str | None = None


class Profile(BaseModel):
    subject: Subject
    facts: list[Fact] = Field(default_factory=list)
    results: list[SourceResult] = Field(default_factory=list)

    def by_type(self) -> dict[FactType, list[Fact]]:
        grouped: dict[FactType, list[Fact]] = {}
        for fact in self.facts:
            grouped.setdefault(fact.type, []).append(fact)
        return grouped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/models.py tests/test_models.py
git commit -m "feat: domain models and enums"
```

---

### Task 3: Input validation and normalization

**Files:**
- Create: `src/nifresearch/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `def is_valid_israeli_id(raw: str) -> bool` — validates the ת"ז check digit (left-pads to 9 digits).
  - `def normalize_id(raw: str) -> str|None` — returns 9-digit zero-padded ID if it is all digits and ≤9 long and valid, else `None`.
  - `def normalize_phone(raw: str) -> str|None` — strips spaces/dashes/parens; returns digits (with leading `+` preserved) or `None` if fewer than 9 digits.
  - `def looks_like_email(raw: str) -> bool` — minimal `x@y.z` check.

- [ ] **Step 1: Write the failing test**

`tests/test_validation.py`:
```python
from nifresearch.validation import (
    is_valid_israeli_id, normalize_id, normalize_phone, looks_like_email,
)


def test_valid_israeli_ids():
    assert is_valid_israeli_id("123456782") is True
    assert is_valid_israeli_id("000000018") is True
    # short IDs are left-padded to 9 digits
    assert is_valid_israeli_id("18") is True


def test_invalid_israeli_ids():
    assert is_valid_israeli_id("123456789") is False
    assert is_valid_israeli_id("abc") is False
    assert is_valid_israeli_id("1234567890") is False  # too long


def test_normalize_id():
    assert normalize_id(" 123456782 ") == "123456782"
    assert normalize_id("18") == "000000018"
    assert normalize_id("123456789") is None


def test_normalize_phone():
    assert normalize_phone("054-123-4567") == "0541234567"
    assert normalize_phone("+972 54 123 4567") == "+972541234567"
    assert normalize_phone("123") is None


def test_looks_like_email():
    assert looks_like_email("a@b.co") is True
    assert looks_like_email("not-an-email") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.validation'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/validation.py`:
```python
from __future__ import annotations

import re


def is_valid_israeli_id(raw: str) -> bool:
    digits = (raw or "").strip()
    if not digits.isdigit() or len(digits) > 9:
        return False
    digits = digits.zfill(9)
    total = 0
    for i, ch in enumerate(digits):
        n = int(ch) * (1 if i % 2 == 0 else 2)
        total += n if n < 10 else n - 9
    return total % 10 == 0


def normalize_id(raw: str) -> str | None:
    digits = (raw or "").strip()
    if not is_valid_israeli_id(digits):
        return None
    return digits.zfill(9)


def normalize_phone(raw: str) -> str | None:
    raw = (raw or "").strip()
    plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 9:
        return None
    return ("+" + digits) if plus else digits


def looks_like_email(raw: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (raw or "").strip()))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_validation.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/validation.py tests/test_validation.py
git commit -m "feat: Israeli ID checksum and input normalization"
```

---

### Task 4: Source plugin contract and registry

**Files:**
- Create: `src/nifresearch/sources/__init__.py`, `src/nifresearch/sources/base.py`
- Test: `tests/test_sources_base.py`

**Interfaces:**
- Consumes: `Subject`, `SourceResult`, `Classification`, `InputField` from `models`.
- Produces:
  - `class Source(ABC)` with class attributes `id: str`, `name: str`, `classification: Classification`, `required_inputs: set[InputField]`; method `can_run(self, subject: Subject) -> bool` (True iff subject has ANY of `required_inputs`); abstract `async def query(self, subject: Subject) -> SourceResult`.
  - `class SourceRegistry` with `register(self, source: Source) -> None`, `all(self) -> list[Source]`, `get(self, source_id: str) -> Source|None`.

- [ ] **Step 1: Write the failing test**

`tests/test_sources_base.py`:
```python
from nifresearch.models import (
    Classification, InputField, Subject, SourceResult, SourceStatus,
)
from nifresearch.sources.base import Source, SourceRegistry


class DummySource(Source):
    id = "dummy"
    name = "Dummy"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    async def query(self, subject):
        return SourceResult(source_id=self.id, status=SourceStatus.OK)


def test_can_run_requires_any_input():
    src = DummySource()
    assert src.can_run(Subject(name_he="דוד")) is True
    assert src.can_run(Subject(email="a@b.co")) is False


def test_registry_register_and_lookup():
    reg = SourceRegistry()
    src = DummySource()
    reg.register(src)
    assert reg.all() == [src]
    assert reg.get("dummy") is src
    assert reg.get("missing") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sources_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.sources'`

- [ ] **Step 3: Write the implementation**

Create empty `src/nifresearch/sources/__init__.py`:
```python
```

`src/nifresearch/sources/base.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod

from nifresearch.models import Classification, InputField, SourceResult, Subject


class Source(ABC):
    id: str
    name: str
    classification: Classification
    required_inputs: set[InputField]

    def can_run(self, subject: Subject) -> bool:
        return bool(self.required_inputs & subject.available_inputs())

    @abstractmethod
    async def query(self, subject: Subject) -> SourceResult:
        ...


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: list[Source] = []

    def register(self, source: Source) -> None:
        self._sources.append(source)

    def all(self) -> list[Source]:
        return list(self._sources)

    def get(self, source_id: str) -> Source | None:
        for s in self._sources:
            if s.id == source_id:
                return s
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sources_base.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/sources/__init__.py src/nifresearch/sources/base.py tests/test_sources_base.py
git commit -m "feat: source plugin contract and registry"
```

---

### Task 5: Mock source plugin

**Files:**
- Create: `src/nifresearch/sources/mock.py`
- Test: `tests/test_mock_source.py`

**Interfaces:**
- Consumes: `Source` from `sources.base`; models.
- Produces: `class MockBoardSource(Source)` (id `"mock_board"`, classification `OFFICIAL_PUBLIC`, required_inputs `{InputField.NAME}`) whose `query` returns a deterministic `SourceResult` with two facts (a `BOARD_MEMBERSHIP` and a `ROLE`) when a name is present, else `NO_MATCH`.

- [ ] **Step 1: Write the failing test**

`tests/test_mock_source.py`:
```python
import pytest

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.mock import MockBoardSource


def test_metadata():
    src = MockBoardSource()
    assert src.id == "mock_board"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
async def test_query_returns_deterministic_facts():
    src = MockBoardSource()
    result = await src.query(Subject(name_he="דוד כהן"))
    assert result.status == SourceStatus.OK
    assert result.source_id == "mock_board"
    types = {f.type for f in result.facts}
    assert FactType.BOARD_MEMBERSHIP in types
    assert FactType.ROLE in types
    assert all(f.source_id == "mock_board" for f in result.facts)


@pytest.mark.asyncio
async def test_query_no_name_is_no_match():
    result = await MockBoardSource().query(Subject(email="a@b.co"))
    assert result.status == SourceStatus.NO_MATCH
    assert result.facts == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mock_source.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.sources.mock'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/sources/mock.py`:
```python
from __future__ import annotations

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source


class MockBoardSource(Source):
    id = "mock_board"
    name = "Mock Board Memberships (sample data)"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    async def query(self, subject: Subject) -> SourceResult:
        name = subject.name_he or subject.name_en
        if not name:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        facts = [
            Fact(
                type=FactType.BOARD_MEMBERSHIP,
                value="עמותת דוגמה לחינוך",
                source_id=self.id,
                confidence=0.4,
                detail={"note": "sample data, not a real record"},
            ),
            Fact(
                type=FactType.ROLE,
                value="חבר ועד",
                source_id=self.id,
                confidence=0.4,
            ),
        ]
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mock_source.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/sources/mock.py tests/test_mock_source.py
git commit -m "feat: deterministic mock board source"
```

---

### Task 6: Compliance gating

**Files:**
- Create: `src/nifresearch/compliance.py`
- Test: `tests/test_compliance.py`

**Interfaces:**
- Consumes: `Classification`, `ComplianceMode`.
- Produces: `def allowed_classifications(mode: ComplianceMode) -> set[Classification]` and `def is_allowed(classification: Classification, mode: ComplianceMode) -> bool`.
  - STRICT → `{OFFICIAL_PUBLIC}`; STANDARD → `{OFFICIAL_PUBLIC, LICENSED}`; PERMISSIVE → all three.

- [ ] **Step 1: Write the failing test**

`tests/test_compliance.py`:
```python
from nifresearch.models import Classification, ComplianceMode
from nifresearch.compliance import allowed_classifications, is_allowed


def test_strict_allows_only_official():
    assert allowed_classifications(ComplianceMode.STRICT) == {Classification.OFFICIAL_PUBLIC}
    assert is_allowed(Classification.OFFICIAL_PUBLIC, ComplianceMode.STRICT) is True
    assert is_allowed(Classification.LICENSED, ComplianceMode.STRICT) is False
    assert is_allowed(Classification.GREY_MARKET, ComplianceMode.STRICT) is False


def test_standard_adds_licensed():
    assert is_allowed(Classification.LICENSED, ComplianceMode.STANDARD) is True
    assert is_allowed(Classification.GREY_MARKET, ComplianceMode.STANDARD) is False


def test_permissive_allows_all():
    assert is_allowed(Classification.GREY_MARKET, ComplianceMode.PERMISSIVE) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_compliance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.compliance'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/compliance.py`:
```python
from __future__ import annotations

from nifresearch.models import Classification, ComplianceMode

_ALLOWED: dict[ComplianceMode, set[Classification]] = {
    ComplianceMode.STRICT: {Classification.OFFICIAL_PUBLIC},
    ComplianceMode.STANDARD: {Classification.OFFICIAL_PUBLIC, Classification.LICENSED},
    ComplianceMode.PERMISSIVE: {
        Classification.OFFICIAL_PUBLIC,
        Classification.LICENSED,
        Classification.GREY_MARKET,
    },
}


def allowed_classifications(mode: ComplianceMode) -> set[Classification]:
    return set(_ALLOWED[mode])


def is_allowed(classification: Classification, mode: ComplianceMode) -> bool:
    return classification in _ALLOWED[mode]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_compliance.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/compliance.py tests/test_compliance.py
git commit -m "feat: compliance classification gating"
```

---

### Task 7: Orchestrator (concurrent fan-out)

**Files:**
- Create: `src/nifresearch/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `Source`, `SourceRegistry`, `is_allowed`, models.
- Produces: `async def run(subject: Subject, sources: list[Source], mode: ComplianceMode, timeout: float = 10.0) -> list[SourceResult]`.
  - For each source: if `not is_allowed(source.classification, mode)` → `SourceResult(status=SKIPPED, error="blocked by compliance mode")`; elif `not source.can_run(subject)` → `SourceResult(status=SKIPPED, error="missing required inputs")`; else `await asyncio.wait_for(source.query(subject), timeout)`, catching `TimeoutError`/`Exception` → `SourceResult(status=ERROR, error=str(e))`. Eligible queries run concurrently via `asyncio.gather`. Order of returned results matches `sources` order.

- [ ] **Step 1: Write the failing test**

`tests/test_orchestrator.py`:
```python
import asyncio
import pytest

from nifresearch.models import (
    Classification, ComplianceMode, InputField, Subject, SourceResult, SourceStatus,
)
from nifresearch.sources.base import Source
from nifresearch.orchestrator import run


class OkSource(Source):
    id = "ok"
    name = "ok"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    async def query(self, subject):
        return SourceResult(source_id=self.id, status=SourceStatus.OK)


class LicensedSource(OkSource):
    id = "lic"
    classification = Classification.LICENSED


class BoomSource(OkSource):
    id = "boom"

    async def query(self, subject):
        raise RuntimeError("kaboom")


class SlowSource(OkSource):
    id = "slow"

    async def query(self, subject):
        await asyncio.sleep(5)
        return SourceResult(source_id=self.id, status=SourceStatus.OK)


@pytest.mark.asyncio
async def test_skips_blocked_and_missing_inputs():
    subject = Subject(name_he="דוד")
    results = await run(subject, [OkSource(), LicensedSource()], ComplianceMode.STRICT)
    by_id = {r.source_id: r for r in results}
    assert by_id["ok"].status == SourceStatus.OK
    assert by_id["lic"].status == SourceStatus.SKIPPED
    assert "compliance" in by_id["lic"].error


@pytest.mark.asyncio
async def test_skips_when_inputs_missing():
    results = await run(Subject(email="a@b.co"), [OkSource()], ComplianceMode.STRICT)
    assert results[0].status == SourceStatus.SKIPPED
    assert "inputs" in results[0].error


@pytest.mark.asyncio
async def test_query_exception_becomes_error():
    results = await run(Subject(name_he="דוד"), [BoomSource()], ComplianceMode.STRICT)
    assert results[0].status == SourceStatus.ERROR
    assert "kaboom" in results[0].error


@pytest.mark.asyncio
async def test_timeout_becomes_error():
    results = await run(Subject(name_he="דוד"), [SlowSource()], ComplianceMode.STRICT, timeout=0.05)
    assert results[0].status == SourceStatus.ERROR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.orchestrator'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/orchestrator.py`:
```python
from __future__ import annotations

import asyncio

from nifresearch.compliance import is_allowed
from nifresearch.models import ComplianceMode, SourceResult, SourceStatus, Subject
from nifresearch.sources.base import Source


async def _run_one(source: Source, subject: Subject, mode: ComplianceMode, timeout: float) -> SourceResult:
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
    try:
        return await asyncio.wait_for(source.query(subject), timeout)
    except (TimeoutError, asyncio.TimeoutError):
        return SourceResult(source_id=source.id, status=SourceStatus.ERROR, error="timed out")
    except Exception as exc:  # noqa: BLE001 — record any source failure
        return SourceResult(source_id=source.id, status=SourceStatus.ERROR, error=str(exc))


async def run(
    subject: Subject,
    sources: list[Source],
    mode: ComplianceMode,
    timeout: float = 10.0,
) -> list[SourceResult]:
    return await asyncio.gather(*(_run_one(s, subject, mode, timeout) for s in sources))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: async orchestrator with compliance/input gating"
```

---

### Task 8: Resolution / merge into a Profile

**Files:**
- Create: `src/nifresearch/resolution.py`
- Test: `tests/test_resolution.py`

**Interfaces:**
- Consumes: models.
- Produces: `def build_profile(subject: Subject, results: list[SourceResult]) -> Profile`.
  - Collects facts from all `OK` results into `Profile.facts` (preserving source order), keeps the full `results` list on the profile, and deduplicates facts that share the same `(type, value)` by keeping the highest-confidence one and recording the contributing source ids in `detail["also_from"]`.

- [ ] **Step 1: Write the failing test**

`tests/test_resolution.py`:
```python
from nifresearch.models import (
    Fact, FactType, Profile, SourceResult, SourceStatus, Subject,
)
from nifresearch.resolution import build_profile


def test_collects_only_ok_facts():
    ok = SourceResult(
        source_id="a", status=SourceStatus.OK,
        facts=[Fact(type=FactType.ROLE, value="חבר ועד", source_id="a")],
    )
    skipped = SourceResult(source_id="b", status=SourceStatus.SKIPPED)
    profile = build_profile(Subject(), [ok, skipped])
    assert len(profile.facts) == 1
    assert profile.results == [ok, skipped]


def test_dedupes_same_type_value_keeping_highest_confidence():
    f_low = Fact(type=FactType.ROLE, value="חבר ועד", source_id="a", confidence=0.3)
    f_high = Fact(type=FactType.ROLE, value="חבר ועד", source_id="b", confidence=0.9)
    r = [
        SourceResult(source_id="a", status=SourceStatus.OK, facts=[f_low]),
        SourceResult(source_id="b", status=SourceStatus.OK, facts=[f_high]),
    ]
    profile = build_profile(Subject(), r)
    assert len(profile.facts) == 1
    kept = profile.facts[0]
    assert kept.confidence == 0.9
    assert set(kept.detail["also_from"]) == {"a", "b"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resolution.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.resolution'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/resolution.py`:
```python
from __future__ import annotations

from nifresearch.models import Fact, Profile, SourceResult, SourceStatus, Subject


def build_profile(subject: Subject, results: list[SourceResult]) -> Profile:
    best: dict[tuple, Fact] = {}
    contributors: dict[tuple, set[str]] = {}
    order: list[tuple] = []

    for result in results:
        if result.status != SourceStatus.OK:
            continue
        for fact in result.facts:
            key = (fact.type, fact.value)
            contributors.setdefault(key, set()).add(fact.source_id)
            if key not in best:
                best[key] = fact.model_copy(deep=True)
                order.append(key)
            elif fact.confidence > best[key].confidence:
                kept_detail = best[key].detail
                best[key] = fact.model_copy(deep=True)
                best[key].detail = {**kept_detail, **best[key].detail}

    facts: list[Fact] = []
    for key in order:
        fact = best[key]
        fact.detail["also_from"] = sorted(contributors[key])
        facts.append(fact)

    return Profile(subject=subject, facts=facts, results=results)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resolution.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/resolution.py tests/test_resolution.py
git commit -m "feat: resolution layer merging results into a profile"
```

---

### Task 9: Shared CKAN client

**Files:**
- Create: `src/nifresearch/sources/ckan.py`
- Test: `tests/test_ckan.py`

**Interfaces:**
- Consumes: `httpx`.
- Produces: `class CkanClient` with `__init__(self, base_url: str, client: httpx.AsyncClient | None = None)` and `async def datastore_search(self, resource_id: str, q: str | None = None, limit: int = 25) -> list[dict]`.
  - Calls `GET {base_url}/api/3/action/datastore_search` with params `resource_id`, optional `q`, `limit`; returns `response.json()["result"]["records"]`; returns `[]` if `success` is falsy.

- [ ] **Step 1: Write the failing test**

`tests/test_ckan.py`:
```python
import httpx
import pytest
import respx

from nifresearch.sources.ckan import CkanClient


@pytest.mark.asyncio
@respx.mock
async def test_datastore_search_returns_records():
    route = respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "result": {"records": [{"x": 1}, {"x": 2}]}},
        )
    )
    async with httpx.AsyncClient() as client:
        ckan = CkanClient("https://data.gov.il", client=client)
        records = await ckan.datastore_search("res-id", q="דוד", limit=10)
    assert records == [{"x": 1}, {"x": 2}]
    assert route.calls.last.request.url.params["resource_id"] == "res-id"
    assert route.calls.last.request.url.params["q"] == "דוד"


@pytest.mark.asyncio
@respx.mock
async def test_datastore_search_handles_failure():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": False})
    )
    async with httpx.AsyncClient() as client:
        records = await CkanClient("https://data.gov.il", client=client).datastore_search("r")
    assert records == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ckan.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.sources.ckan'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/sources/ckan.py`:
```python
from __future__ import annotations

import httpx


class CkanClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client

    async def datastore_search(
        self, resource_id: str, q: str | None = None, limit: int = 25
    ) -> list[dict]:
        params: dict[str, object] = {"resource_id": resource_id, "limit": limit}
        if q:
            params["q"] = q
        url = f"{self.base_url}/api/3/action/datastore_search"

        async def _do(client: httpx.AsyncClient) -> list[dict]:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success"):
                return []
            return payload["result"]["records"]

        if self._client is not None:
            return await _do(self._client)
        async with httpx.AsyncClient() as client:
            return await _do(client)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ckan.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/sources/ckan.py tests/test_ckan.py
git commit -m "feat: shared async CKAN client"
```

---

### Task 10: data.gov.il Amutot source

**Files:**
- Create: `src/nifresearch/sources/datagov_amutot.py`
- Test: `tests/test_datagov_amutot.py`

**Interfaces:**
- Consumes: `Source`, `CkanClient`, models.
- Produces: `class AmutotSource(Source)` — id `"datagov_amutot"`, classification `OFFICIAL_PUBLIC`, required_inputs `{InputField.NAME}`. Constructor `__init__(self, client: httpx.AsyncClient | None = None)`. Constants `BASE_URL = "https://data.gov.il"`, `RESOURCE_ID = "be5b7935-3922-45d4-9638-08871b17ec95"`. `query` searches by the subject's name; each matched amuta record becomes an `ORG_AFFILIATION` fact whose `value` is the org name field `"שם עמותה"`, with `detail` carrying the amuta number `"מספר עמותה"` and status. `NO_MATCH` if no records.

- [ ] **Step 1: Write the failing test**

`tests/test_datagov_amutot.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.datagov_amutot import AmutotSource


def test_metadata():
    src = AmutotSource()
    assert src.id == "datagov_amutot"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
@respx.mock
async def test_query_maps_records_to_facts():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": [
            {"שם עמותה": "עמותת אור", "מספר עמותה": "580001", "סטטוס עמותה": "רשומה"},
        ]}})
    )
    async with httpx.AsyncClient() as client:
        result = await AmutotSource(client=client).query(Subject(name_he="אור"))
    assert result.status == SourceStatus.OK
    assert result.facts[0].type == FactType.ORG_AFFILIATION
    assert result.facts[0].value == "עמותת אור"
    assert result.facts[0].detail["amuta_number"] == "580001"
    assert result.facts[0].source_id == "datagov_amutot"


@pytest.mark.asyncio
@respx.mock
async def test_query_no_records_is_no_match():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    async with httpx.AsyncClient() as client:
        result = await AmutotSource(client=client).query(Subject(name_he="איןכזה"))
    assert result.status == SourceStatus.NO_MATCH
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datagov_amutot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.sources.datagov_amutot'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/sources/datagov_amutot.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source
from nifresearch.sources.ckan import CkanClient

BASE_URL = "https://data.gov.il"
RESOURCE_ID = "be5b7935-3922-45d4-9638-08871b17ec95"


class AmutotSource(Source):
    id = "datagov_amutot"
    name = "data.gov.il — Non-profits (Amutot)"
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
        facts = [
            Fact(
                type=FactType.ORG_AFFILIATION,
                value=rec.get("שם עמותה", "").strip(),
                source_id=self.id,
                confidence=0.3,
                url="https://www.guidestar.org.il/",
                detail={
                    "amuta_number": str(rec.get("מספר עמותה", "")),
                    "status": rec.get("סטטוס עמותה", ""),
                },
            )
            for rec in records
            if rec.get("שם עמותה")
        ]
        if not facts:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datagov_amutot.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/sources/datagov_amutot.py tests/test_datagov_amutot.py
git commit -m "feat: data.gov.il amutot source"
```

> **Note on confidence (applies to all live sources):** a name match against an
> entity registry is weak evidence that the *person* is affiliated — the registry
> is not person-indexed (see catalog §1). Keep `confidence` low (≈0.3) and let the
> report present these as candidates, per spec §11.

---

### Task 11: data.gov.il Companies source

**Files:**
- Create: `src/nifresearch/sources/datagov_companies.py`
- Test: `tests/test_datagov_companies.py`

**Interfaces:**
- Consumes: `Source`, `CkanClient`, models.
- Produces: `class CompaniesSource(Source)` — id `"datagov_companies"`, classification `OFFICIAL_PUBLIC`, required_inputs `{InputField.NAME}`. Constructor `__init__(self, client=None)`. `BASE_URL = "https://data.gov.il"`, `RESOURCE_ID = "f004176c-b85f-4542-8901-7b3176f9a054"`. Each record becomes an `ORG_AFFILIATION` fact: value = company name `"שם חברה"`, detail carries company number `"מספר חברה"` and status `"סטטוס חברה"`.

- [ ] **Step 1: Write the failing test**

`tests/test_datagov_companies.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.datagov_companies import CompaniesSource


def test_metadata():
    src = CompaniesSource()
    assert src.id == "datagov_companies"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
@respx.mock
async def test_query_maps_records_to_facts():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": [
            {"שם חברה": "אור בע\"מ", "מספר חברה": "510001", "סטטוס חברה": "פעילה"},
        ]}})
    )
    async with httpx.AsyncClient() as client:
        result = await CompaniesSource(client=client).query(Subject(name_he="אור"))
    assert result.status == SourceStatus.OK
    assert result.facts[0].type == FactType.ORG_AFFILIATION
    assert result.facts[0].value == "אור בע\"מ"
    assert result.facts[0].detail["company_number"] == "510001"


@pytest.mark.asyncio
@respx.mock
async def test_query_no_records_is_no_match():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    async with httpx.AsyncClient() as client:
        result = await CompaniesSource(client=client).query(Subject(name_he="איןכזה"))
    assert result.status == SourceStatus.NO_MATCH
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datagov_companies.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/sources/datagov_companies.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source
from nifresearch.sources.ckan import CkanClient

BASE_URL = "https://data.gov.il"
RESOURCE_ID = "f004176c-b85f-4542-8901-7b3176f9a054"


class CompaniesSource(Source):
    id = "datagov_companies"
    name = "data.gov.il — Companies Registrar"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._ckan = CkanClient(BASE_URL, client=client)

    async def query(self, subject: Subject) -> SourceResult:
        name = subject.name_he or subject.name_en
        if not name:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        records = await self._ckan.datastore_search(RESOURCE_ID, q=name, limit=10)
        facts = [
            Fact(
                type=FactType.ORG_AFFILIATION,
                value=rec.get("שם חברה", "").strip(),
                source_id=self.id,
                confidence=0.3,
                url="https://ica.justice.gov.il/",
                detail={
                    "company_number": str(rec.get("מספר חברה", "")),
                    "status": rec.get("סטטוס חברה", ""),
                },
            )
            for rec in records
            if rec.get("שם חברה")
        ]
        if not facts:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datagov_companies.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/sources/datagov_companies.py tests/test_datagov_companies.py
git commit -m "feat: data.gov.il companies source"
```

---

### Task 12: Israel Bar lawyers source

**Files:**
- Create: `src/nifresearch/sources/bar_lawyers.py`
- Test: `tests/test_bar_lawyers.py`

**Interfaces:**
- Consumes: `Source`, `CkanClient`, models.
- Produces: `class BarLawyersSource(Source)` — id `"bar_lawyers"`, classification `OFFICIAL_PUBLIC`, required_inputs `{InputField.NAME}`. Constructor `__init__(self, client=None)`. `BASE_URL = "https://www.odata.org.il"`, `RESOURCE_ID = "320c0980-3b41-4d3a-aa25-5f3f0a4a9b50"` (placeholder — see note below). Each record becomes a `PROFESSION` fact (value `"עורך/ת דין"`) plus a `LICENSE` fact carrying the membership number and city from record fields `"שם מלא"`, `"מספר חבר"`, `"עיר"`.

> **Resource-ID note for the implementer:** the exact `odata.org.il` resource id for
> the Bar members dataset must be confirmed at build time (catalog §4.1 links the
> dataset page `https://www.odata.org.il/dataset/israelbarmembers`). The tests mock
> HTTP, so they pass regardless; before wiring it live, open the dataset page, copy
> the active `resource_id`, and update the `RESOURCE_ID` constant. The field names in
> the test (`"שם מלא"`, `"מספר חבר"`, `"עיר"`) are representative — adjust to the live
> schema and update the test to match if they differ.

- [ ] **Step 1: Write the failing test**

`tests/test_bar_lawyers.py`:
```python
import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.bar_lawyers import BarLawyersSource


def test_metadata():
    src = BarLawyersSource()
    assert src.id == "bar_lawyers"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
@respx.mock
async def test_query_maps_records_to_profession_and_license():
    respx.get("https://www.odata.org.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": [
            {"שם מלא": "דוד כהן", "מספר חבר": "12345", "עיר": "תל אביב"},
        ]}})
    )
    async with httpx.AsyncClient() as client:
        result = await BarLawyersSource(client=client).query(Subject(name_he="דוד כהן"))
    assert result.status == SourceStatus.OK
    types = {f.type for f in result.facts}
    assert FactType.PROFESSION in types
    assert FactType.LICENSE in types
    license_fact = next(f for f in result.facts if f.type == FactType.LICENSE)
    assert license_fact.detail["member_number"] == "12345"
    assert license_fact.detail["city"] == "תל אביב"


@pytest.mark.asyncio
@respx.mock
async def test_query_no_records_is_no_match():
    respx.get("https://www.odata.org.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    async with httpx.AsyncClient() as client:
        result = await BarLawyersSource(client=client).query(Subject(name_he="איןכזה"))
    assert result.status == SourceStatus.NO_MATCH
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bar_lawyers.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/sources/bar_lawyers.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source
from nifresearch.sources.ckan import CkanClient

BASE_URL = "https://www.odata.org.il"
# TODO(build-time): confirm the live resource id from
# https://www.odata.org.il/dataset/israelbarmembers
RESOURCE_ID = "320c0980-3b41-4d3a-aa25-5f3f0a4a9b50"


class BarLawyersSource(Source):
    id = "bar_lawyers"
    name = "Israel Bar — Lawyers register"
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
            member = str(rec.get("מספר חבר", ""))
            city = rec.get("עיר", "")
            facts.append(Fact(
                type=FactType.PROFESSION, value="עורך/ת דין",
                source_id=self.id, confidence=0.4,
                url="https://www.israelbar.org.il/",
                detail={"member_number": member, "city": city},
            ))
            facts.append(Fact(
                type=FactType.LICENSE, value=f"חבר/ת לשכה {member}".strip(),
                source_id=self.id, confidence=0.4,
                detail={"member_number": member, "city": city},
            ))
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_bar_lawyers.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/sources/bar_lawyers.py tests/test_bar_lawyers.py
git commit -m "feat: Israel Bar lawyers source"
```

---

### Task 13: Default registry setup

**Files:**
- Create: `src/nifresearch/registry_setup.py`
- Test: `tests/test_registry_setup.py`

**Interfaces:**
- Consumes: `SourceRegistry` and all source classes.
- Produces: `def build_default_registry(client: httpx.AsyncClient | None = None) -> SourceRegistry` registering, in order: `MockBoardSource()`, `AmutotSource(client)`, `CompaniesSource(client)`, `BarLawyersSource(client)`.

- [ ] **Step 1: Write the failing test**

`tests/test_registry_setup.py`:
```python
from nifresearch.registry_setup import build_default_registry


def test_default_registry_contains_expected_sources():
    reg = build_default_registry()
    ids = [s.id for s in reg.all()]
    assert ids == ["mock_board", "datagov_amutot", "datagov_companies", "bar_lawyers"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_registry_setup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.registry_setup'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/registry_setup.py`:
```python
from __future__ import annotations

import httpx

from nifresearch.sources.base import SourceRegistry
from nifresearch.sources.bar_lawyers import BarLawyersSource
from nifresearch.sources.datagov_amutot import AmutotSource
from nifresearch.sources.datagov_companies import CompaniesSource
from nifresearch.sources.mock import MockBoardSource


def build_default_registry(client: httpx.AsyncClient | None = None) -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(MockBoardSource())
    registry.register(AmutotSource(client))
    registry.register(CompaniesSource(client))
    registry.register(BarLawyersSource(client))
    return registry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_registry_setup.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/registry_setup.py tests/test_registry_setup.py
git commit -m "feat: default source registry"
```

---

### Task 14: Subject-building helper from raw form input

**Files:**
- Create: `src/nifresearch/intake.py`
- Test: `tests/test_intake.py`

**Interfaces:**
- Consumes: `Subject`, validation helpers.
- Produces: `def build_subject(name_he, name_en, email, phone, id_number) -> tuple[Subject, list[str]]` where each arg is `str | None`. Normalizes phone and ID; returns the `Subject` plus a list of human-readable warnings (e.g. invalid ID, invalid email). An invalid ID is dropped from the subject and a warning is added; same for an unparseable phone.

- [ ] **Step 1: Write the failing test**

`tests/test_intake.py`:
```python
from nifresearch.intake import build_subject


def test_valid_inputs_pass_through():
    subject, warnings = build_subject("דוד כהן", None, "d@e.co", "054-123-4567", "123456782")
    assert subject.name_he == "דוד כהן"
    assert subject.email == "d@e.co"
    assert subject.phone == "0541234567"
    assert subject.id_number == "123456782"
    assert warnings == []


def test_invalid_id_dropped_with_warning():
    subject, warnings = build_subject(None, "David", None, None, "123456789")
    assert subject.id_number is None
    assert any("ID" in w or "ת\"ז" in w for w in warnings)


def test_invalid_email_warns():
    subject, warnings = build_subject("דוד", None, "bad-email", None, None)
    assert subject.email is None
    assert any("email" in w.lower() for w in warnings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_intake.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.intake'`

- [ ] **Step 3: Write the implementation**

`src/nifresearch/intake.py`:
```python
from __future__ import annotations

from nifresearch.models import Subject
from nifresearch.validation import looks_like_email, normalize_id, normalize_phone


def build_subject(
    name_he: str | None,
    name_en: str | None,
    email: str | None,
    phone: str | None,
    id_number: str | None,
) -> tuple[Subject, list[str]]:
    warnings: list[str] = []

    clean_email = (email or "").strip() or None
    if clean_email and not looks_like_email(clean_email):
        warnings.append(f"Ignored invalid email: {clean_email}")
        clean_email = None

    clean_phone = None
    if phone and phone.strip():
        clean_phone = normalize_phone(phone)
        if clean_phone is None:
            warnings.append(f"Ignored unparseable phone: {phone.strip()}")

    clean_id = None
    if id_number and id_number.strip():
        clean_id = normalize_id(id_number)
        if clean_id is None:
            warnings.append(f'Ignored invalid Israeli ID (ת"ז): {id_number.strip()}')

    subject = Subject(
        name_he=(name_he or "").strip() or None,
        name_en=(name_en or "").strip() or None,
        email=clean_email,
        phone=clean_phone,
        id_number=clean_id,
    )
    return subject, warnings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_intake.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nifresearch/intake.py tests/test_intake.py
git commit -m "feat: intake helper building a validated Subject"
```

---

### Task 15: Web app (form + report) with RTL templates

**Files:**
- Create: `src/nifresearch/web/__init__.py`, `src/nifresearch/web/app.py`
- Create: `src/nifresearch/web/templates/form.html`, `src/nifresearch/web/templates/report.html`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `build_subject`, `build_default_registry`, `orchestrator.run`, `build_profile`, `ComplianceMode`.
- Produces: `app` (a FastAPI instance) with `GET /` → the form and `POST /research` → the rendered report. Uses `httpx.AsyncClient` per request and STRICT compliance mode. The report displays warnings, grouped facts with source ids, and a per-source status table (queried/skipped/errored).

- [ ] **Step 1: Write the failing test**

`tests/test_web.py`:
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
def test_research_renders_report_with_facts_and_provenance():
    # All live CKAN calls return empty; the mock source still produces facts.
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    respx.get("https://www.odata.org.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד כהן"})
    assert resp.status_code == 200
    # mock_board fact appears, tagged with its source
    assert "חבר ועד" in resp.text
    assert "mock_board" in resp.text
    # report is RTL
    assert 'dir="rtl"' in resp.text


@respx.mock
def test_research_warns_on_invalid_id():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    respx.get("https://www.odata.org.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד", "id_number": "123456789"})
    assert resp.status_code == 200
    assert "123456789" in resp.text  # surfaced as a warning
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_web.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nifresearch.web'` (and note: `TestClient` requires `httpx`, already installed)

- [ ] **Step 3: Write the implementation**

Create empty `src/nifresearch/web/__init__.py`:
```python
```

`src/nifresearch/web/app.py`:
```python
from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from nifresearch.intake import build_subject
from nifresearch.models import ComplianceMode
from nifresearch.orchestrator import run
from nifresearch.registry_setup import build_default_registry
from nifresearch.resolution import build_profile

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
) -> HTMLResponse:
    subject, warnings = build_subject(name_he, name_en, email, phone, id_number)
    async with httpx.AsyncClient() as client:
        registry = build_default_registry(client)
        results = await run(subject, registry.all(), ComplianceMode.STRICT)
    profile = build_profile(subject, results)
    return TEMPLATES.TemplateResponse(
        request,
        "report.html",
        {
            "subject": subject,
            "warnings": warnings,
            "groups": profile.by_type(),
            "results": profile.results,
            "registry": {s.id: s.name for s in registry.all()},
        },
    )
```

`src/nifresearch/web/templates/form.html`:
```html
<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>NIFResearch — מחקר תורמים</title>
  <style>
    body { font-family: sans-serif; max-width: 640px; margin: 2rem auto; }
    label { display:block; margin: .5rem 0 .15rem; }
    input { width: 100%; padding: .4rem; }
    button { margin-top: 1rem; padding: .5rem 1rem; }
    .note { color:#555; font-size:.9rem; }
  </style>
</head>
<body>
  <h1>מחקר תורמים</h1>
  <p class="note">הזינו כל פרט מזהה שיש לכם. כל השדות אופציונליים.</p>
  <form action="/research" method="post">
    <label>שם (עברית)</label><input name="name_he">
    <label>Name (English)</label><input name="name_en">
    <label>אימייל / Email</label><input name="email">
    <label>טלפון / Phone</label><input name="phone">
    <label>תעודת זהות / ID</label><input name="id_number">
    <button type="submit">חפש</button>
  </form>
</body>
</html>
```

`src/nifresearch/web/templates/report.html`:
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

  {% for w in warnings %}
    <div class="warn">{{ w }}</div>
  {% endfor %}

  {% if not groups %}
    <p>לא נמצאו ממצאים מהמקורות הזמינים.</p>
  {% endif %}

  {% for fact_type, facts in groups.items() %}
    <h2>{{ fact_type.value }}</h2>
    {% for f in facts %}
      <div class="fact">
        {{ f.value }}
        <span class="src">
          — מקור: {{ registry.get(f.source_id, f.source_id) }}
          (ביטחון {{ "%.1f"|format(f.confidence) }}){% if f.url %},
          <a href="{{ f.url }}">קישור</a>{% endif %}
        </span>
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
  <p><a href="/">חיפוש חדש</a></p>
</body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_web.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/nifresearch/web tests/test_web.py
git commit -m "feat: FastAPI web app with RTL form and report"
```

---

### Task 16: Run script and README

**Files:**
- Modify: `README.md`
- Test: manual (documented run)

**Interfaces:**
- Consumes: `nifresearch.web.app:app`.
- Produces: documented launch command.

- [ ] **Step 1: Write the README**

Replace `README.md`:
```markdown
# NIFResearch

Prototype Israeli prospect-research tool. Given any subset of {name, email,
phone, Israeli ID}, it queries pluggable official-public data sources and
renders an RTL report. Results are not stored. See
`docs/superpowers/specs/` and `docs/superpowers/research/source-catalog.md`.

## Run

```bash
uv run uvicorn nifresearch.web.app:app --reload
```

Open http://127.0.0.1:8000 . Compliance mode is STRICT (official-public sources
only). The `mock_board` source returns sample data for demos.

## Test

```bash
uv run pytest
```

## Adding a source

Implement `nifresearch.sources.base.Source` (set `id`, `name`,
`classification`, `required_inputs`, and `async query`) and register it in
`nifresearch/registry_setup.py`.
```

- [ ] **Step 2: Verify the app launches**

Run: `uv run uvicorn nifresearch.web.app:app --port 8001 &` then `sleep 2 && curl -s localhost:8001/ | grep -q name_he && echo OK` then stop the server.
Expected: prints `OK`

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README with run and extension instructions"
```

---

## Self-Review

**1. Spec coverage:**
- Pluggable source contract → Task 4. Mock plugin → Task 5. Live slice (data.gov.il amutot+companies, Bar lawyers) → Tasks 10–12. Orchestrator concurrent fan-out + input gating → Task 7. Compliance gating / classification + STRICT default → Tasks 6, 15. Resolution/merge with provenance → Task 8. ת"ז checksum → Task 3. RTL report with provenance + skipped-sources section → Task 15. No persistence → Task 15 (per-request client, no DB). Subject with optional identifiers → Task 2. README/run → Task 16. Catalog deliverable → already committed (`307de1b`).
- Out-of-scope items (auth, DB, CRM, scraping, international, GuideStar scrape) are correctly absent.

**2. Placeholder scan:** The only deliberate "TODO" is the Bar `RESOURCE_ID` (Task 12), explicitly flagged with build-time instructions because the live id must be copied from the dataset page; tests are HTTP-mocked and pass regardless. All other steps contain complete code.

**3. Type consistency:** `Source` attributes (`id`, `name`, `classification`, `required_inputs`, `query`) are used identically in Tasks 4, 5, 10–13, 15. `SourceResult`/`Fact`/`Subject`/`Profile` fields match Task 2 throughout. `build_subject` signature (Task 14) matches its call in Task 15. `build_default_registry(client)` (Task 13) matches its use in Task 15. `run(subject, sources, mode, timeout)` (Task 7) matches Task 15's call. `build_profile(subject, results)` (Task 8) matches Task 15. CKAN `datastore_search(resource_id, q, limit)` (Task 9) matches Tasks 10–12.
