# NIFResearch v0.3 — Grey-market sources + report-link fix

**Date:** 2026-06-28
**Status:** Approved design — pending implementation plan
**Builds on:** v0.2 (`2026-06-28-nifresearch-v0.2-design.md`)

## Motivation

Two things in one iteration:

1. **Report-link bug.** The provenance `קישור` link in the report points at
   `https://data.gov.il/dataset/<slug>`, which **404s on a hard click** —
   data.gov.il is a single-page app whose dataset deep-links do not resolve when
   opened cold (the slugs are valid in the API; the SPA renders its own 404).
   Links also do not open in a new tab.
2. **Grey-market sources.** Add 10 commercial data-broker / enrichment sources to
   demonstrate (and later enable) grey-market enrichment, gated behind the
   PERMISSIVE compliance mode. Context from the user: this will not be shown to
   NIF and will be run past their legal advisors before any real use; the
   strictness dropdown restricts it.

### Firm exclusion (non-negotiable)

**Breach-sourced datasets are excluded** — the leaked population/voter registry
dumps ("Agron 2006", "Elector 2020") documented in the source catalog §6. Processing
stolen national-ID data is unlawful regardless of gating, and such leaks are often
the real data behind cheap "people-search" results. The 10 providers below are
commercial broker APIs (dual-use), not breach mirrors.

## 1. Report-link fix

- **Open in a new tab:** every external link in `_report_body.html` gets
  `target="_blank" rel="noopener noreferrer"`.
- **Fix the 404:** change the three data.gov.il sources' provenance `url` (and
  their constant, e.g. `DATASET_URL`) from the SPA dataset page to the
  always-loadable CKAN API page:
  - amutot → `https://data.gov.il/api/3/action/package_show?id=moj-amutot`
  - companies → `https://data.gov.il/api/3/action/package_show?id=ica_companies`
  - doctors → `https://data.gov.il/api/3/action/package_show?id=database-of-doctors-licenses-moh`
  The human-facing site already lives in each fact's `detail` (guidestar /
  registrar; doctors keep the dataset reference) and is unchanged.
- Update the affected source unit tests to assert the new `url` values.

## 2. Compliance gating (no change needed)

`compliance.py` already maps PERMISSIVE → includes `GREY_MARKET`, and the
orchestrator skips sources whose classification is not allowed. Adding
`GREY_MARKET` sources to the default registry means: under STRICT (default) and
STANDARD they appear as **"blocked by compliance mode"** in the status table;
only PERMISSIVE runs them. Default mode stays STRICT.

## 3. `FactType.CONTACT`

Add one enum member `CONTACT = "contact"` to `FactType` for contact-channel facts
(emails, phones, caller-name). Everything else reuses existing types
(`ADDRESS`, `EMPLOYER`, `ROLE`, etc.).

## 4. `GreySource` base class

`src/nifresearch/sources/grey/base.py` — `class GreySource(Source)`:

- Class attrs each subclass sets: `id`, `name`, `url`, `env_var: str`,
  `required_inputs`. `classification = Classification.GREY_MARKET` (fixed on the
  base).
- `__init__(self, client: httpx.AsyncClient | None = None, api_key: str | None = None)`:
  stores `client`; `self._api_key = api_key if api_key is not None else os.getenv(env_var)`.
- `is_configured(self) -> bool`: `bool(self._api_key)`.
- `async query(self, subject) -> SourceResult`:
  - if not `is_configured()` → `SourceResult(status=SKIPPED, error="not configured: set <env_var>")`.
  - else call `facts = await self._fetch(subject, client)` (using the passed
    client, or a fresh `httpx.AsyncClient()` if none); wrap exceptions →
    `ERROR(str(exc))`; empty facts → `NO_MATCH`; otherwise `OK` with facts.
  - Subclasses implement `async def _fetch(self, subject, client) -> list[Fact]`
    (their endpoint, auth, request, and response→`Fact` mapping).
- Every `Fact` a subclass emits carries `source_id=self.id`,
  `confidence=0.25` (grey = weak/unverified), `url=self.url`, and
  `detail["caveat"] = "grey-market source — verify legal basis before use"`.
- A small helper on the base, `_grey_fact(type, value, **detail) -> Fact`, builds
  facts with these defaults so subclasses stay tiny and consistent.

**Two-key providers (Twilio):** the base's single `env_var` doesn't fit Twilio's
SID+token. `TwilioLookupSource` overrides `__init__`/`is_configured` to read
`NIFRESEARCH_TWILIO_SID` + `NIFRESEARCH_TWILIO_TOKEN` and use HTTP basic auth.

## 5. The 10 grey providers

All `GREY_MARKET`, key-gated, in `src/nifresearch/sources/grey/`. Exact endpoints
and response fields are representative and **must be confirmed against current
provider docs before real use** (the implementation + tests pin a concrete shape;
mocked tests pass regardless).

| # | Class / file | Inputs | Env key(s) | Maps to |
|---|---|---|---|---|
| 1 | `PiplSource` `pipl.py` | name/email/phone | `NIFRESEARCH_PIPL_API_KEY` | ADDRESS, EMPLOYER, CONTACT |
| 2 | `LushaSource` `lusha.py` | name+company/email | `NIFRESEARCH_LUSHA_API_KEY` | EMPLOYER, ROLE, CONTACT |
| 3 | `HunterSource` `hunter.py` | email | `NIFRESEARCH_HUNTER_API_KEY` | CONTACT |
| 4 | `NumVerifySource` `numverify.py` | phone | `NIFRESEARCH_NUMVERIFY_KEY` | CONTACT, ADDRESS |
| 5 | `TwilioLookupSource` `twilio_lookup.py` | phone | `NIFRESEARCH_TWILIO_SID`+`_TOKEN` | CONTACT |
| 6 | `ApolloSource` `apollo.py` | name+company/email | `NIFRESEARCH_APOLLO_API_KEY` | EMPLOYER, ROLE, CONTACT |
| 7 | `RocketReachSource` `rocketreach.py` | name/email | `NIFRESEARCH_ROCKETREACH_API_KEY` | CONTACT, EMPLOYER |
| 8 | `ContactOutSource` `contactout.py` | email | `NIFRESEARCH_CONTACTOUT_API_KEY` | CONTACT |
| 9 | `ClearbitSource` `clearbit.py` | email | `NIFRESEARCH_CLEARBIT_API_KEY` | EMPLOYER, CONTACT |
| 10 | `PeopleDataLabsSource` `peopledatalabs.py` | name/email/phone | `NIFRESEARCH_PDL_API_KEY` | EMPLOYER, ADDRESS, CONTACT |

`required_inputs` semantics are unchanged (source runs if the subject has ANY of
its inputs). Providers needing a company domain (Hunter email-finder, Lusha/Apollo
by name) use the email/phone path or are best-effort with what's available;
where a needed field is absent the subclass returns no facts → `NO_MATCH`.

## 6. Registry

`build_default_registry` registers the three data.gov.il sources first, then the
10 grey sources (passing the shared client). Order: amutot, companies, doctors,
then pipl, lusha, hunter, numverify, twilio, apollo, rocketreach, contactout,
clearbit, peopledatalabs (13 total). The grey sources accept the same `client`
argument for uniformity (they may ignore it and open their own when needed).

## 7. Report banner

When any `GREY_MARKET` source ran (status not SKIPPED-by-compliance — i.e. it was
allowed and executed), show a prominent banner in the report:
"⚠️ מקורות אפורים (grey-market) נשאלו — יש לוודא בסיס חוקי לפני הסתמכות."
Implementation: pass a `grey_ids: set[str]` (source ids whose classification is
GREY_MARKET) into the template context; the fragment shows the banner if any
result whose `source_id` is in `grey_ids` has status `ok`/`no_match`/`error`
(i.e. actually ran, not compliance-skipped). The form note near the dropdown is
updated to say grey sources now exist and require PERMISSIVE + a configured key.

## 8. Testing

- **Base:** `GreySource` not-configured → SKIPPED; configured+facts → OK;
  configured+empty → NO_MATCH; `_fetch` exception → ERROR. (Use a tiny test
  subclass.)
- **Per provider (respx-mocked):** configured+match → expected facts (assert a
  representative fact's type/value/confidence/url/caveat); not-configured →
  SKIPPED; configured+no-match → NO_MATCH. Twilio: also the two-env-var config.
- **Orchestrator integration:** a grey source is `SKIPPED` ("blocked by
  compliance mode") under STRICT and runs (keyed, mocked) under PERMISSIVE.
- **Registry:** all 13 ids present in order.
- **Web:** the grey banner appears when a grey source ran (PERMISSIVE + mocked
  key) and is absent under STRICT; links carry `target="_blank"`.
- All HTTP mocked with respx; no network, no real keys.

## 9. Docs / safety

- `docs/superpowers/research/grey-sources.md`: a bold "**DO NOT ENABLE WITHOUT
  LEGAL SIGN-OFF**" header, then one row per provider — what it is, what it
  returns, the env key, and its legal/consent posture. Restate the breach-data
  exclusion.
- README: a short "Grey-market sources" section — disabled by default (need
  PERMISSIVE **and** a key), env-var names, and the legal caveat.

## 10. Out of scope (YAGNI)

- Real API calls / committed keys (never).
- Breach datasets (excluded by policy).
- Caching, rate-limiting, retries/backoff.
- Per-provider response-schema exhaustiveness (representative mapping only).
- A company-domain input field (providers needing it degrade to NO_MATCH).

## 11. Version

Next push bumps the version and tags it (0.1.2 → 0.1.3).
