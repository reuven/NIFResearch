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
