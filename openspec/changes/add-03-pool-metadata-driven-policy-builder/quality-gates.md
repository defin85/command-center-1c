# Quality Gates (add-03-pool-metadata-driven-policy-builder)

Дата: 2026-02-26

## OpenSpec validate

Команда:

`openspec validate add-03-pool-metadata-driven-policy-builder --strict --no-interactive`

Результат:

- exit code: `0`
- ключевая строка: `Change 'add-03-pool-metadata-driven-policy-builder' is valid`

## OpenAPI contract build/check

Команды:

- `./contracts/scripts/build-orchestrator-openapi.sh build`
- `./contracts/scripts/build-orchestrator-openapi.sh check`

Результат:

- обе команды завершились с `exit code: 0`
- ключевые строки:
  - `Bundle updated: /home/egor/code/command-center-1c/contracts/orchestrator/openapi.yaml`
  - `Bundle is up to date: /home/egor/code/command-center-1c/contracts/orchestrator/openapi.yaml`

## Backend targeted tests

Команда:

`./.venv/bin/pytest -q orchestrator/apps/intercompany_pools/tests/test_metadata_catalog.py orchestrator/apps/api_v2/tests/test_pool_runs_openapi_contract_parity.py orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py -k "metadata_catalog or referential_error_for_unknown_metadata_field or referential_error_for_unknown_table_part or referential_error_for_unknown_row_field or invalid_link_to or invalid_link_rules_depends_on or snapshot_unavailable_with_unified_error_shape or returns_conflict_when_lock_is_busy or problem_details_error_schema_supports_field_and_referential_error_shapes"`

Результат:

- `20 passed`
- `81 deselected`
- `0 failed`

## Frontend targeted tests

Команда:

`cd frontend && npm run test:run -- src/pages/Pools/__tests__/PoolCatalogPage.test.tsx`

Результат:

- `Test Files 1 passed (1)`
- `Tests 27 passed (27)`
- `0 failed`
- были предупреждения React `act(...)`, но тестовый прогон успешно завершён.
