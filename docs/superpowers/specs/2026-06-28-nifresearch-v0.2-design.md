# NIFResearch v0.2 — Usable Results, Live Progress, Strictness Control

**Date:** 2026-06-28
**Status:** Approved design — pending implementation plan
**Builds on:** `2026-06-26-nifresearch-prospect-research-design.md` (v0.1 prototype)

## Motivation

First real-world use of the v0.1 prototype surfaced three problems:

1. **Fake data pollutes every search.** The `mock_board` demo source is in the
   default registry and returns the same fabricated facts (`עמותת דוגמה לחינוך`,
   `חבר ועד`) for any name.
2. **The Israel Bar source 404s.** Its odata.org.il "dataset" is not a queryable
   API — it is a stale Excel file (last updated Jan 2023) + a PDF
   (`datastore_active: false`). There is no `datastore_search` endpoint, so the
   source can never work as built.
3. **Timeouts.** data.gov.il's CKAN API is slow (~3.5s per call measured, spiky
   under concurrency), tripping the 10s per-source timeout.

Separately, the user asked for (a) **progress feedback** after submitting a
search and (b) a way to **configure source strictness**, which is currently
hardcoded to `ComplianceMode.STRICT` at `web/app.py` with no config surface.

### Inherent limitation (carried from the v0.1 research)

Searching the amutot/companies registries **by a person's name** matches
*organization names* containing that string — it does **not** find organizations
the person is affiliated with (Israel has no person→org index). For a donor's
name these sources will mostly return noise or `no_match`. The genuinely useful
person-keyed source is a **professional registry**; the doctors registry is the
one that is both name-searchable and queryable via API.

## Scope

A single iteration covering four changes: source cleanup, timeout increase,
strictness dropdown, and live per-source progress via Server-Sent Events (SSE).

## 1. Source registry changes

- **Delete `MockBoardSource` entirely** — remove `src/nifresearch/sources/mock.py`
  and `tests/test_mock_source.py`, and drop it from `registry_setup`. No fake
  data in the product.
- **Delete `BarLawyersSource` entirely** — remove
  `src/nifresearch/sources/bar_lawyers.py` and `tests/test_bar_lawyers.py`. There
  is no queryable Bar endpoint.
- **Add `DoctorsSource`** (`src/nifresearch/sources/datagov_doctors.py`):
  - `id = "datagov_doctors"`, `name = "data.gov.il — Doctors registry (MoH)"`,
    `classification = OFFICIAL_PUBLIC`, `required_inputs = {InputField.NAME}`.
  - `BASE_URL = "https://data.gov.il"`,
    `RESOURCE_ID = "9c64c522-bbc2-48fe-96fb-3b2a8626f59e"` (verified
    datastore-active, 63,768 records, name-searchable).
  - `query`: search by subject name (`name_he or name_en`) via the shared
    `CkanClient`. For each record produce:
    - a `PROFESSION` fact, value `"רופא/ה"`;
    - a `LICENSE` fact, value built from the license number, with
      `detail["license_number"]` from field `"מספר רישיון רופא"`,
      `detail["specialty"]` from field `"שם התמחות"`, and
      `detail["full_name"]` from `"שם פרטי"` + `"שם משפחה"`.
  - Both facts: `source_id="datagov_doctors"`, `confidence=0.4`,
    `url="https://data.gov.il/dataset/database-of-doctors-licenses-moh"`.
  - `NO_MATCH` when no records; `limit=10`.
- **Default registry** becomes, in order: `AmutotSource`, `CompaniesSource`,
  `DoctorsSource` — all `official_public`, all via the shared CKAN client.

## 2. Timeout

Raise the orchestrator's default per-source `timeout` from `10.0` to `25.0`
seconds. Timeouts still map to `SourceStatus.ERROR` as before.

## 3. Strictness dropdown

- Add `<select name="compliance_mode">` to the form with options STRICT
  (default/selected), STANDARD, PERMISSIVE.
- Add a parsing helper `parse_compliance_mode(raw: str | None) -> ComplianceMode`
  that maps the string to the enum, defaulting to `STRICT` on missing/unknown
  input.
- The web layer passes the parsed mode to the orchestrator (replacing the
  hardcoded `ComplianceMode.STRICT`).
- A one-line note under the dropdown: loosening has no effect until
  licensed/grey-market sources exist (all current sources are `official_public`).

## 4. Live per-source progress (SSE)

### Orchestrator

Add an async generator
`run_streaming(subject, sources, mode, timeout=25.0) -> AsyncIterator[SourceResult]`
that yields each source's `SourceResult` **as it becomes available**:
- Skipped sources (blocked by compliance, or missing inputs) yield their
  `SKIPPED` result immediately.
- Eligible sources run concurrently; results yield via `asyncio.as_completed`
  as each finishes.
- Each yielded `SourceResult` already carries `source_id`, so the consumer can
  match it to the source list.

The existing `run()` stays for the non-streaming path and tests. To avoid
duplicated gating logic, both `run()` and `run_streaming()` reuse the existing
`_run_one(...)` helper.

### Web flow

1. The form POSTs to `/research`. `/research` no longer does the work
   synchronously. It builds the `Subject` + warnings, parses the compliance
   mode, computes the **eligible source list** (those that would run vs. be
   skipped, with reasons), and renders a **progress page** (`research.html`):
   - subject summary + input warnings;
   - a list of source rows, each "pending", plus a progress bar (`done/total`);
   - JS that opens an `EventSource` to `/research/stream` with the search
     params + compliance mode in the query string.
2. `GET /research/stream` (SSE, `media_type="text/event-stream"`) rebuilds the
   same `Subject`/mode, runs `run_streaming(...)`, and emits:
   - one `progress` event per source as it completes:
     `data: {"source_id", "name", "status", "fact_count"}`;
   - a final `done` event whose data is a JSON object `{"html": "..."}` carrying
     the **rendered report fragment** (grouped facts with provenance + the
     per-source status table). The HTML is JSON-encoded because SSE `data:`
     fields cannot contain raw newlines; the JS parses it and injects `.html`.
     The `progress` events are likewise JSON objects on a single `data:` line.
3. The progress-page JS updates each row + the bar on each `progress` event,
   and on `done` injects the report fragment into the page.

### Templates

- `form.html` — add the compliance dropdown.
- `research.html` — progress skeleton + JS (EventSource consumer).
- `_report_body.html` — report fragment (grouped facts + status table),
  extracted from the current `report.html` so it can be rendered standalone for
  the SSE `done` payload.
- A `<noscript>` note on `research.html` stating that live progress requires
  JavaScript.

### Shared helper

A single helper builds `(Subject, warnings, ComplianceMode)` from the raw form/
query params, used by both `/research` and `/research/stream`, to keep param
handling DRY.

## 5. Privacy note

`EventSource` is GET-only, so search params (including ת"ז) appear in the
`/research/stream` query string. Nothing is persisted and the app is local, but
this is a minor deviation from the privacy posture; a future change could switch
to a streaming `fetch` POST. Accepted for the prototype. Until the stream is
moved to POST, operators should run with `--no-access-log` (or apply a log
filter for this path), because a server access log would otherwise capture the
ID-bearing URL.

## 6. Testing

- `DoctorsSource`: respx-mocked unit tests — metadata; record→PROFESSION+LICENSE
  mapping (assert specialty, license number, confidence, url); `NO_MATCH` on no
  records.
- `run_streaming`: yields exactly one `SourceResult` per input source, including
  a skipped one; all expected `source_id`s present.
- `parse_compliance_mode`: maps "strict"/"standard"/"permissive" and defaults to
  STRICT on `None`/garbage.
- Web (`TestClient` + respx): form contains the dropdown and the three modes;
  `/research` returns the progress skeleton listing the eligible source names;
  `/research/stream` yields SSE events ending in a `done` event containing report
  markup. Mocked CKAN responses drive at least one real fact (via doctors or
  amutot) so the `done` fragment shows a fact with provenance.
- Remove `tests/test_mock_source.py` and `tests/test_bar_lawyers.py`; rebuild
  `test_web.py` so it no longer depends on the deleted mock source.

## 7. Out of scope (YAGNI)

- A no-JS fallback that renders the full report without SSE.
- A server-side job store / persistence.
- Exact full-name matching (we keep simple `q` token search).
- Cancellation of in-flight source queries.
- Styling polish beyond a functional progress bar.

## 8. Version

Per project policy, the next push bumps the version and tags it (0.1.1 → 0.1.2).
