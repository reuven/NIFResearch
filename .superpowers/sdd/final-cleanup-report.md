# Final Review Cleanup Report

## Branch
`feature/prototype`

## Changes Made

### 1. `pyproject.toml` — Suppress `StarletteDeprecationWarning`
Added `filterwarnings` under `[tool.pytest.ini_options]`:
```toml
filterwarnings = [
    "ignore:Using `httpx` with `starlette.testclient` is deprecated",
]
```
Note: the warning class is `StarletteDeprecationWarning` (not a subclass of `DeprecationWarning`), so the message-only pattern (no category qualifier) is required to match it.

### 2. `tests/test_resolution.py` — Remove unused import, add reverse-order dedup test
- Removed `Profile` from the import line (was unused, F401).
- Added `test_dedupes_high_confidence_first_seen` which exercises the case where the higher-confidence fact arrives first in the results list, verifying the dedup logic retains the best confidence and records all contributing source IDs in `detail["also_from"]`.

### 3. `tests/test_compliance.py` — Strengthen set-equality assertions
- `test_standard_adds_licensed`: added `assert allowed_classifications(ComplianceMode.STANDARD) == {Classification.OFFICIAL_PUBLIC, Classification.LICENSED}`
- `test_permissive_allows_all`: added `assert allowed_classifications(ComplianceMode.PERMISSIVE) == {Classification.OFFICIAL_PUBLIC, Classification.LICENSED, Classification.GREY_MARKET}`
- All existing assertions preserved.

### 4. `src/nifresearch/web/app.py` — Capture registry map inside `async with` block
Moved `registry.all()` call to inside the `async with httpx.AsyncClient()` block, capturing the result in `registry_map`. This ensures the registry is not accessed after the client is closed. Template context unchanged (key still `"registry"`).

### 5. `src/nifresearch/web/templates/form.html` — Accessibility `for`/`id` pairs
Added matching `id` attribute to each `<input>` and `for` attribute to each `<label>`, e.g.:
```html
<label for="name_he">שם (עברית)</label><input id="name_he" name="name_he">
```
All five fields updated. No other markup changes.

## Test Run Output (full, pristine)

```
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.1.1, pluggy-1.6.0
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.14.1, asyncio-1.4.0, respx-0.23.1
asyncio: mode=Mode.AUTO
collected 47 items

tests/test_bar_lawyers.py::test_metadata PASSED                          [  2%]
tests/test_bar_lawyers.py::test_query_maps_records_to_profession_and_license PASSED [  4%]
tests/test_bar_lawyers.py::test_query_no_records_is_no_match PASSED      [  6%]
tests/test_ckan.py::test_datastore_search_returns_records PASSED         [  8%]
tests/test_ckan.py::test_datastore_search_handles_failure PASSED         [ 10%]
tests/test_compliance.py::test_strict_allows_only_official PASSED        [ 12%]
tests/test_compliance.py::test_standard_adds_licensed PASSED             [ 14%]
tests/test_compliance.py::test_permissive_allows_all PASSED              [ 17%]
tests/test_datagov_amutot.py::test_metadata PASSED                       [ 19%]
tests/test_datagov_amutot.py::test_query_maps_records_to_facts PASSED    [ 21%]
tests/test_datagov_amutot.py::test_records_missing_org_name_is_no_match PASSED [ 23%]
tests/test_datagov_amutot.py::test_query_no_records_is_no_match PASSED   [ 25%]
tests/test_datagov_companies.py::test_metadata PASSED                    [ 27%]
tests/test_datagov_companies.py::test_query_maps_records_to_facts PASSED [ 29%]
tests/test_datagov_companies.py::test_query_no_records_is_no_match PASSED [ 31%]
tests/test_datagov_companies.py::test_records_missing_company_name_is_no_match PASSED [ 34%]
tests/test_intake.py::test_valid_inputs_pass_through PASSED              [ 36%]
tests/test_intake.py::test_invalid_id_dropped_with_warning PASSED        [ 38%]
tests/test_intake.py::test_invalid_email_warns PASSED                    [ 40%]
tests/test_intake.py::test_invalid_phone_dropped_with_warning PASSED     [ 42%]
tests/test_intake.py::test_empty_strings_become_none_without_warning PASSED [ 44%]
tests/test_mock_source.py::test_metadata PASSED                          [ 46%]
tests/test_mock_source.py::test_query_returns_deterministic_facts PASSED [ 48%]
tests/test_mock_source.py::test_query_no_name_is_no_match PASSED         [ 51%]
tests/test_models.py::test_enum_values PASSED                            [ 53%]
tests/test_models.py::test_subject_available_inputs PASSED               [ 55%]
tests/test_models.py::test_profile_groups_facts_by_type PASSED           [ 57%]
tests/test_orchestrator.py::test_skips_blocked_and_missing_inputs PASSED [ 59%]
tests/test_orchestrator.py::test_skips_when_inputs_missing PASSED        [ 61%]
tests/test_orchestrator.py::test_query_exception_becomes_error PASSED    [ 63%]
tests/test_orchestrator.py::test_timeout_becomes_error PASSED            [ 65%]
tests/test_orchestrator.py::test_eligible_sources_run_concurrently PASSED [ 68%]
tests/test_registry_setup.py::test_default_registry_contains_expected_sources PASSED [ 70%]
tests/test_resolution.py::test_collects_only_ok_facts PASSED             [ 72%]
tests/test_resolution.py::test_dedupes_same_type_value_keeping_highest_confidence PASSED [ 74%]
tests/test_resolution.py::test_dedupes_high_confidence_first_seen PASSED [ 76%]
tests/test_smoke.py::test_package_imports PASSED                         [ 78%]
tests/test_sources_base.py::test_can_run_requires_any_input PASSED       [ 80%]
tests/test_sources_base.py::test_registry_register_and_lookup PASSED     [ 82%]
tests/test_validation.py::test_valid_israeli_ids PASSED                  [ 85%]
tests/test_validation.py::test_invalid_israeli_ids PASSED                [ 87%]
tests/test_validation.py::test_normalize_id PASSED                       [ 89%]
tests/test_validation.py::test_normalize_phone PASSED                    [ 91%]
tests/test_validation.py::test_looks_like_email PASSED                   [ 93%]
tests/test_web.py::test_form_renders PASSED                              [ 95%]
tests/test_web.py::test_research_renders_report_with_facts_and_provenance PASSED [ 97%]
tests/test_web.py::test_research_warns_on_invalid_id PASSED              [100%]

============================== 47 passed in 0.57s ==============================
```

## Notes / Concerns
- The `filterwarnings` pattern omits the category qualifier because `StarletteDeprecationWarning` is not a subclass of `DeprecationWarning`; the message-only pattern (`ignore:<message>`) suppresses it correctly.
- All runtime behavior is unchanged; no source, orchestrator, or resolution logic was modified.
