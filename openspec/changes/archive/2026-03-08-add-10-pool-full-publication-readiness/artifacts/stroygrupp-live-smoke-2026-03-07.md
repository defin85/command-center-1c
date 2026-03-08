# `stroygrupp` Backend Integration + Live Browser Smoke (`2026-03-07`)

## Scope
Закрываем два acceptance proof для baseline:
- backend integration test полного top-down цикла с read-model projection;
- live browser smoke поверх реального UI/API/OData без моков.

Базовый сценарий:
- tenant: `default`
- database: `stroygrupp_7751284461`
- pool: `stroygrupp-full-publication-baseline`
- actor: `admin`
- actor IB mapping: `ГлавБух / 22022`
- direction: `top_down`
- mode: `unsafe`
- `run_input.starting_amount = 12956834.00`

## Backend Integration Proof
Новый integration test:
- file: `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py`
- test: `test_top_down_pool_run_read_model_projects_publication_attempts_and_verification_after_internal_completion`

Что проверяет:
1. public `POST /api/v2/pools/runs/` создаёт `top_down` run;
2. internal status update завершает execution `completed`;
3. publication result проецируется в `PoolPublicationAttempt`;
4. run report/read-model показывает:
   - `status = published`
   - `workflow_status = completed`
   - `publication_step_state = completed`
   - `verification_status = passed`
   - `mismatches_count = 0`

Подтверждённый targeted run:
- `./scripts/dev/pytest.sh -q apps/api_v2/tests/test_intercompany_pool_runs.py -k top_down_pool_run_read_model_projects_publication_attempts_and_verification_after_internal_completion`
- result: `1 passed, 89 deselected`

## Live Browser Smoke Proof
Новый env-gated browser spec:
- file: `frontend/tests/browser/pools-live-publication-smoke.spec.ts`

Что делает:
1. получает JWT через реальный `/api/token`;
2. резолвит active tenant через `/api/v2/tenants/list-my-tenants/`;
3. открывает `/pools/runs`;
4. выбирает pool `stroygrupp-full-publication-baseline`;
5. через UI выполняет `Create / Upsert Run` для `top_down + unsafe`;
6. в `Inspect` ждёт `verification_status = passed`.

Команда:
- `cd frontend && CC1C_POOLS_LIVE=1 CC1C_POOLS_LIVE_USERNAME=admin CC1C_POOLS_LIVE_PASSWORD='p-123456' npm exec playwright test tests/browser/pools-live-publication-smoke.spec.ts`

Результат:
- `1 passed`

## Live Run Fact
Подтверждённый live run, созданный/переиспользованный в этой проверке:
- `PoolRun.id = fc79dd29-ddeb-4d39-ae9f-be9cc66a5424`
- `WorkflowExecution.id = 8e648dc3-4473-4c63-9374-6c18dc52d9fa`

Read-model report показал:
- `status = published`
- `workflow_status = completed`
- `approval_state = not_required`
- `publication_step_state = completed`
- `master_data_gate.status = completed`
- `verification_status = passed`
- `verification_summary.checked_targets = 1`
- `verification_summary.verified_documents = 1`
- `verification_summary.mismatches_count = 0`

## Requirement -> Code -> Test
- `run report должен проецировать publication attempts и verification status после completion`
  - Code:
    - `orchestrator/apps/api_internal/views_workflows.py`
    - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - Test:
    - `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py::test_top_down_pool_run_read_model_projects_publication_attempts_and_verification_after_internal_completion`

- `UI должен позволять оператору пройти baseline сценарий через Create/Inspect и увидеть passed verification`
  - Code:
    - `frontend/src/pages/Pools/PoolRunsPage.tsx`
    - `frontend/tests/browser/pools-live-publication-smoke.spec.ts`
  - Test:
    - `frontend/tests/browser/pools-live-publication-smoke.spec.ts`
    - `frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx`

## Outcome
Для baseline `stroygrupp -> Document_РеализацияТоваровУслуг -> Услуги` теперь есть два независимых acceptance proof:
- deterministic backend integration proof на read-model/projection уровне;
- live UI proof на реальном runtime/OData пути.
