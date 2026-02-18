# E2E regression report: run 500 on 3 organizations

Дата: 2026-02-18
Задача: `command-center-1c-bqza.25`

## 1) Scenario definition

Проверен end-to-end regression path после migration на worker `odata-core`:
- `500` документов распределены по `3` target DB (`200 + 150 + 150`);
- статус публикации `partial_success` (2 success target + 1 failed target);
- для failed target сохранены retry attempts и canonical diagnostics.

Контур проверки:
- update workflow status (internal endpoint) с worker-style publication result payload;
- facade details/report (`/api/v2/pools/runs/{run_id}/`, `/api/v2/pools/runs/{run_id}/report/`);
- совместимость `publication_attempts`, `publication_summary`, `attempts_by_status`, diagnostics.

## 2) Test evidence

Добавлен regression test:
- `orchestrator/apps/api_internal/tests/test_views_workflows.py`
- `test_worker_publication_projection_e2e_regression_run_500_on_3_targets`

Проверяет:
- status projection: `partial_success`, `workflow_status=completed`, `publication_step_state=completed`;
- summary projection: `total_targets=3`, `succeeded_targets=2`, `failed_targets=1`, `max_attempts=5`;
- report compatibility: `publication_attempts=5`, `attempts_by_status={success:2, failed:3}`;
- failed-target diagnostics: `domain_error_code=POOL_RUNTIME_PUBLICATION_ODATA_FAILED`, `http_error.status=503`, `payload_summary.documents_count=150`.

## 3) Commands and results

1. Targeted regression subset:
```bash
./.venv/bin/pytest -q orchestrator/apps/api_internal/tests/test_views_workflows.py -k 'run_500_on_3_targets or worker_publication_projection_preserves_pool_run_report_contract or completed_is_idempotent_for_projected_publication_attempts'
```
Результат: `3 passed`.

2. Full API-internal regression slice:
```bash
./.venv/bin/pytest -q orchestrator/apps/api_internal/tests/test_views_workflows.py orchestrator/apps/api_internal/tests/test_pool_runtime_bridge_openapi_contract.py
```
Результат: `30 passed`.

## 4) Verdict

E2E regression для сценария `run 500 on 3 organizations` прошёл без контрактных расхождений.
Go/no-go по задаче `.25`: **GO**.
