# Runbook: Pools dual-write / dual-read cutover

## 1. Scope
- Объект cutover: runtime routing `pools/runs*` и safe-команды (`confirm-publication`, `abort-publication`) в unified execution core.
- Объект контроля: dual-write consistency (`pool_run` + `workflow_execution` + Variant A artifacts), dual-read correctness в facade API.
- Non-goal: удаление `workflows` runtime в рамках этого runbook.

## 2. Preconditions
- Завершены задачи:
  - `4.1` link backfill `pool_run -> workflow_run`;
  - `4.2` dual-read historical/transition view;
  - `4.4` tenant linkage/backfill для workflow executions;
  - `4.5` registry preflight decommission (`execution-consumers-registry`);
  - `4.7` OData compatibility preflight (`odata-compatibility-profile`).
- Для safe-команд активен Variant A pipeline:
  - `pool_run_command_log`,
  - `pool_run_command_outbox`,
  - single-winner CAS.

## 3. Cutover Phases
1. `Phase 0: Preflight`
   - Выполнить:
     - `preflight_workflow_decommission_consumers --json`;
     - `preflight_odata_compatibility_profile --configuration-id ... --compatibility-mode ... --release-profile-version ... --json`.
   - Ожидаемый результат: checks PASS (или зафиксированный `No-Go` с блокирующими причинами).
2. `Phase 1: Dual-write on`
   - Create/start path пишет facade + workflow linkage/metadata.
   - Safe-команды пишут command_log/outbox и публикуют side effects только post-commit.
3. `Phase 2: Dual-read enforced`
   - `GET /api/v2/pools/runs*` использует unified projection с fallback на transition linkage.
   - Historical runs остаются читаемыми через совместимый view.
4. `Phase 3: Legacy start disabled`
   - Legacy start path отключён для новых run.
   - Legacy execution используется только как rollback routing target.
5. `Phase 4: Stabilization window`
   - Поддерживается dual-write until stable.
   - Проводится SLI review и принимается решение `Go/No-Go` для завершения окна.

## 4. Rollback Criteria (Blocking)
- `SLO degradation`:
  - sustained рост `command_log write errors` выше baseline/ошибочного бюджета;
  - критический рост `outbox lag`;
  - saturation retry backlog (порог по `dispatch retry saturation`).
- `Tenant boundary incident`:
  - любой подтверждённый cross-tenant data exposure или mismatch tenant linkage.
- `Projection drift`:
  - систематическое расхождение facade status/provenance с workflow runtime state.

При выполнении любого критерия выполняется немедленный rollback routing (см. секцию 5).

## 5. Rollback Path
1. Зафиксировать `No-Go` решение и incident id.
2. Переключить create/start routing обратно на legacy execution path (без schema rollback).
3. Сохранить dual-write данные (`workflow linkage`, `command_log`, `outbox`) для расследования.
4. Отключить дальнейший rollout до завершения RCA и corrective actions.
5. Выполнить post-rollback валидацию:
   - API availability (`/pools/runs*`);
   - tenant confidentiality (`404 RUN_NOT_FOUND` для unknown/cross-tenant);
   - отсутствие потери historical/audit данных.

## 6. Mandatory SLI Snapshot
- Перед `Go` в следующую фазу сохраняется snapshot:
  - `cc1c_orchestrator_pool_run_command_log_write_errors_total`,
  - `cc1c_orchestrator_pool_run_command_outbox_lag_seconds`,
  - `cc1c_orchestrator_pool_run_command_outbox_retry_saturation_ratio`,
  - `cc1c_orchestrator_pool_run_command_outbox_retry_saturated_pending_total`.
- Snapshot должен быть приложен к release артефакту вместе с `profile_version` из OData profile.

## 7. Go/No-Go Decision Template
- `Decision`: `Go` | `No-Go`
- `Window`: `<start/end UTC>`
- `Release profile version`: `<odata profile version>`
- `Registry version`: `<execution-consumers-registry version>`
- `SLI summary`: `<values + trend>`
- `Incidents`: `<none | ids>`
- `Owner approval`: `<platform + pools>`
