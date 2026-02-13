# Deprecation Plan: Legacy pools execution path

## 1. Scope
- Объект deprecation: legacy execution path в `pools`, который формирует run lifecycle без `workflow_core`.
- Объект НЕ в scope этого плана: удаление `workflows` runtime.
- Цель: полностью перевести create/start routing `pools/runs` на unified execution core, сохраняя rollback-путь и compatibility read-path.

## 2. Preconditions
- Выполнены задачи:
  - `4.1` (link backfill `pool_run -> workflow_run`);
  - `4.2` (dual-read для historical/transition runs);
  - `4.4` (tenant linkage/backfill для `workflow_execution` записей `execution_consumer=pools`);
  - `4.5` и `4.6` (registry + transitional non-pools contract).
- Для rollout публикации зафиксирован approved `odata-compatibility-profile.yaml`.
- Для safe-команд включён Variant A (`command_log + outbox + CAS`) и наблюдаемость по lag/error saturation.

## 3. Rollout Phases
1. `Phase A: Observe`
   - Legacy path остаётся доступен только как rollback target.
   - Включены метрики и audit-теги `execution_backend=legacy_pool_runtime` для new create/start.
   - Цель: зафиксировать базовую частоту legacy usage.
2. `Phase B: Workflow-core preferred`
   - Create/start routing по умолчанию направляется в `workflow_core`.
   - Legacy path разрешён только под controlled override (операционный флаг/процедура rollback).
   - Для transition runs применяется dual-read из unified view.
3. `Phase C: Legacy start disabled`
   - Новый старт через legacy path блокируется.
   - Historical/legacy runs продолжают читаться через facade API.
   - Rollback возможен только через управляемый возврат routing, без schema rollback.
4. `Phase D: Post-stabilization`
   - Legacy path остаётся только как read-compatible исторический след.
   - Решение об удалении `workflows` или legacy артефактов принимается отдельным change после consumer preflight (`Go`).

## 4. Go/No-Go Gates
- `Go` в следующую фазу допускается только при выполнении всех условий:
  - `tenant boundary` инциденты = `0`;
  - projection drift (`pool facade` vs `workflow runtime`) в пределах согласованного порога;
  - `command_log write errors` и `outbox retry saturation` не превышают SLO budget;
  - нет блокирующих регрессий UI/API по historical runs/details/audit.
- `No-Go`:
  - переход фазы запрещён;
  - остаёмся в текущей фазе;
  - фиксируем corrective actions.

## 5. Rollback Triggers
- Немедленный rollback routing в legacy path при:
  - блокирующей деградации SLO публикации;
  - инциденте tenant confidentiality/boundary;
  - систематическом projection drift, влияющем на фасадные статусы.
- Rollback правила:
  - rollback затрагивает routing, а не схему данных;
  - linkage и dual-write данные сохраняются для расследования;
  - после rollback выполняется mandatory incident review перед повторным cutover.

## 6. Ownership and Operations
- Owner: platform/backend (`intercompany_pools` + `workflow_core`).
- Required artifacts:
  - release note с текущей фазой deprecation;
  - checklist перехода фазы (go/no-go);
  - post-rollout отчёт по SLI/SLO и rollback decisions.
