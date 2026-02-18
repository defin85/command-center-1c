# Legacy transport cleanup report

Дата: 2026-02-18
Связанная задача: `command-center-1c-bqza.28`

## Цель cleanup

Деактивировать legacy publication transport path в Orchestrator runtime и исключить дублирующий OData side-effect path после Big-bang миграции в worker `odata-core`.

## Code changes

1. `orchestrator/apps/intercompany_pools/pool_domain_steps.py`
- `pool.publication_odata` переведен в deterministic fail-closed behavior:
  - возвращается ошибка `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`;
  - OData side effects в Orchestrator runtime больше не выполняются.
- Удален устаревший execution-код legacy path (`publish_run_documents`/`retry_failed_run_documents` invocation).
- Удалены неиспользуемые helper-функции legacy publication payload normalization.

2. `orchestrator/apps/intercompany_pools/tests/test_pool_domain_steps.py`
- Обновлены тесты publication step:
  - для safe-mode ожидается fail-closed `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`;
  - для unsafe-mode ожидается fail-closed `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`;
  - подтверждено сохранение `publication_step_state` без side effects.

## Verification

```bash
./.venv/bin/pytest -q orchestrator/apps/intercompany_pools/tests/test_pool_domain_steps.py
```
Результат: `4 passed`.

```bash
./.venv/bin/pytest -q \
  orchestrator/apps/api_internal/tests/test_views_workflows.py \
  orchestrator/apps/api_internal/tests/test_pool_runtime_bridge_openapi_contract.py
```
Результат: `30 passed`.

## Cleanup outcome

- Дублирующий publication OData transport-path в Orchestrator runtime деактивирован.
- Единый transport-owner для publication side effects закреплен за worker `odata-core`.
