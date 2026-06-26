# NIFResearch — Israeli Prospect-Research Prototype

**Date:** 2026-06-26
**Status:** Approved design — pending implementation plan

## 1. Purpose

A web-based prototype that helps a non-profit's donor-relations team learn more
about a donor, given whatever basic identifiers they have (name, email, phone,
and/or Israeli ID number / ת"ז). The system compiles a single **report** drawn
from a pluggable set of back-end data sources.

The category of software is **prospect research** (a.k.a. donor research / wealth
screening) — a mainstream part of professional fundraising. US equivalents
include DonorSearch, iWave, and WealthEngine. No comparable tool exists for the
Israeli data ecosystem; this prototype explores what is possible here.

### Primary goal of this prototype

**Explore what is possible.** Research-first: map the Israeli data-source
landscape (legal status, queryability, key required, cost), then build a thin but
genuinely working end-to-end slice that proves the pluggable-source architecture.
The research findings matter as much as the code.

## 2. Legal & privacy context (a primary design driver)

Israel's **Privacy Protection Law (חוק הגנת הפרטיות)** — and especially
**Amendment 13, in force since August 2025** — significantly tightened the rules
for holding and processing databases of personal information, with meaningful
enforcement behind the Privacy Protection Authority.

Key consequences shaping this design:

- It is not only **storage** that is regulated — **use and processing** of
  personal data are too. Re-displaying data, even ephemerally, can count as use.
- Aggregating data keyed on **ת"ז / phone** into a personal profile is exactly
  the activity the law scrutinizes. The ת"ז is the strongest key for official
  records but the most legally sensitive and the least consistently available
  (it may appear on a bank-transfer/cheque donation, but not on a credit-card
  donation).
- There is a meaningful difference between **official public registries**, and
  **scraping / grey-market data** (which is often itself sourced from leaks).

**Design stance:** the live prototype integrates only **official, public**
sources. Grey-market and licensed providers are **fully catalogued** in the
research deliverable (so we understand what is possible) but kept **out of the
live integration**, behind a **disabled-by-default compliance flag**. Getting the
full picture without taking on the exposure. If legal sign-off is later obtained,
enabling a source class is a config change, not a rewrite.

## 3. Architecture

A Python web application with four layers:

1. **Web/API layer** — a form accepting any subset of {name (he/en), email,
   phone, ת"ז}, and a rendered report.
2. **Orchestrator** — validates and normalises the input into a `Subject`,
   selects sources whose required inputs are satisfied AND whose classification
   is permitted by the active compliance mode, runs them **concurrently**, and
   collects results.
3. **Source plugins** — one file per source, implementing a common contract.
4. **Resolution / merge layer** — combines `SourceResult`s into a single
   `Profile`, grouping facts by category, attaching provenance, and flagging
   conflicts.

A dead or slow source must fail gracefully without blocking the others
(async fan-out).

### 3.1 The source plugin contract (the heart of the system)

Each source declares:

- `id`, `name`, `description`
- `required_inputs` — which identifier(s) it needs to run (e.g. company registry
  needs a name or company number; an email-only source needs an email). The
  orchestrator skips sources whose inputs are not satisfied.
- `classification` / `legal_basis` — one of `official_public`, `licensed`,
  `grey_market`. Drives the compliance toggle.
- `async query(subject) -> SourceResult`

Adding a source = adding one file. Core logic never changes. The
"pluggable backend" idea is therefore also a **compliance feature**: each plugin
declares its own legal basis, so sources can be enabled/disabled by class.

## 4. Data model

- **`Subject`** — `name_he`, `name_en`, `email`, `phone`, `id_number`, all
  optional. The ת"ז is checksum-validated; an invalid ת"ז is flagged, not
  silently used.
- **`Fact`** — `type` (e.g. `address`, `employer`, `role`, `board_membership`,
  `donation`, `income_estimate`), `value`, `confidence`, `source_id`,
  `retrieved_at`, `url`. **Every fact carries its own provenance.**
- **`SourceResult`** — `source_id`, `status` (`ok` / `no_match` / `error` /
  `skipped`), `latency`, `facts: list[Fact]`, optional raw payload.
- **`Profile`** — the `Subject` plus merged facts grouped by category, with
  conflicts flagged and full provenance retained.

**Provenance-per-fact** is the central trust/compliance decision: every fact
knows its origin, so results can be audited, filtered by legal basis, and judged
by a human — instead of collapsing into an opaque score.

## 5. The report

Rendered as RTL-aware HTML, grouped by what the donor-relations head asked for:

- **Location** (address — a rough income/affluence signal)
- **Employment / role**
- **Board memberships / directorships**
- **Giving history** (donations to other non-profits)
- **Income proxies**

Every fact shows its **source** and a **confidence indicator**. The report also
includes an honest **"sources skipped"** section explaining which sources could
not run because the right identifier was absent — so the user understands the
report's completeness.

## 6. Privacy posture, baked in

- **No persistence by default** — results are session-ephemeral. Non-storage is
  the architectural default (directly serving the "display but don't store"
  idea).
- Every source is **classification-tagged**; a **compliance mode** disables whole
  classes of source at once (grey-market off by default).
- **Optional audit log of queries made** (not of results retrieved).
- A clear disclaimer / intended-use surface in the UI.

## 7. Research deliverable

`docs/superpowers/research/source-catalog.md` — a map of the Israeli
prospect-research landscape, across categories:

- Official registries (companies, non-profits/עמותות, etc.)
- Non-profit / charity data (GuideStar Israel, רשם העמותות)
- Real-estate / address data
- Professional / employment data
- Social / open web
- **Grey-market data brokers** (catalogued, not integrated)

For each source: contents, required key, access method (API / scrape / manual),
legal status, cost, and notes. This is the core of the "explore what's possible"
goal.

## 8. Live slice (what we actually wire up)

- **GuideStar Israel / Registrar of Non-profits (רשם העמותות)** — board members &
  officers of non-profits. Public.
- **Companies Registrar (רשם החברות)** — directorships. Public (some data behind a
  paid API; we use the public tier).
- **1–2 mock/sample plugins** — to demonstrate the pattern and to develop against
  without hitting live services or real people. Demos should target **public
  figures** (e.g. known philanthropists on non-profit boards) to avoid privacy
  concerns during development.

## 9. Tech stack

- **Python 3.14**, managed with **uv**
- **FastAPI** (async web framework — ideal for slow external fan-out)
- **httpx** (async HTTP client)
- **Pydantic** (models + validation)
- **Jinja2** (RTL-aware HTML report)
- **pytest** (tests)

## 10. Out of scope (YAGNI)

- Authentication / multi-user
- A real database / persistence
- CRM integration
- Batch / scheduled enrichment
- Production-grade scraping infrastructure
- Live international sources (noted in the catalogue only)

## 11. Key engineering risks

- **Entity resolution** is the genuine hard problem: deciding whether a match in
  source A is the same person as a match in source B, especially with common
  Hebrew names and partial identifiers. The prototype surfaces candidates with
  confidence and provenance rather than asserting a single identity.
- **Hebrew / RTL / transliteration**: names cross he/en, and matching must
  tolerate spelling variants.
- **Source fragility**: official registries are slow, rate-limited, and change
  their interfaces; plugins must isolate this.
