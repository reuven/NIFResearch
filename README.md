# NIFResearch

Prototype Israeli prospect-research tool. Given any subset of {name, email,
phone, Israeli ID}, it queries pluggable official-public data sources and
renders an RTL report. Results are not stored. See
`docs/superpowers/specs/` and `docs/superpowers/research/source-catalog.md`.

## Run

```bash
uv run uvicorn nifresearch.web.app:app --reload
```

Open http://127.0.0.1:8000 .

The search form has a **source-strictness** dropdown (STRICT default). After you
submit, a **progress page** shows each source's status live (via SSE) and then
renders the report. Live sources: data.gov.il amutot, companies, and the MoH
doctors registry — all official/public. Results are not stored.

## Privacy note

The live-progress stream (`/research/stream`) is a `GET` endpoint, so search
parameters — including the Israeli ID (ת"ז) — appear in its URL. Nothing is
persisted by the app, but a server **access log** would capture these URLs.
When running beyond local use, disable access logging for this endpoint, e.g.:

```bash
uv run uvicorn nifresearch.web.app:app --no-access-log
```

A future version can switch the stream to a `POST` + `fetch` to remove params
from the URL entirely.

## Grey-market sources (disabled by default)

Ten commercial data-broker / enrichment sources are available but **double-gated**:
they run only under the **PERMISSIVE** strictness setting AND only when their API
key environment variable is set (e.g. `NIFRESEARCH_PIPL_API_KEY`). With no keys,
they report "not configured" and do nothing. See
`docs/superpowers/research/grey-sources.md` for the full list and the legal
caveat — **do not enable for real data without legal sign-off.** Breach-sourced
datasets are never integrated.

## Test

```bash
uv run pytest
```

## Adding a source

Implement `nifresearch.sources.base.Source` (set `id`, `name`,
`classification`, `required_inputs`, and `async query`) and register it in
`nifresearch/registry_setup.py`.
