# Change: Унифицировать исполнение pools через workflow execution core

## Why
Сейчас контур `pools` начал формироваться как самостоятельный runtime с собственными run-состояниями, retry и audit-потоком. Это создаёт риск второй платформы исполнения рядом с уже существующим `workflows` runtime.

Целевой сценарий системы — единый механизм сервисных функций над ИБ (развёртывание, публикация, манипуляции данными) с переиспользованием driver schema и общего execution lifecycle.

Нужен архитектурный разворот: `pools` остаётся доменным модулем, а исполнение переводится в единый workflow execution core.

Дополнительно, после уточнения scope `add-intercompany-pool-distribution-module`, execution-часть намеренно выведена из foundation change и должна быть закрыта здесь.

## What Changes
- Зафиксировать `workflows` как единственный runtime для многошагового исполнения (`Template/Run/Step`, retry, audit, status lifecycle, queueing).
- Зафиксировать `pools` как domain facade + compiler и снять терминологическую неоднозначность:
  - `PoolImportSchemaTemplate` (термин execution-core; алиас foundation-сущности `PoolSchemaTemplate`) остаётся доменным артефактом импорта;
  - совместимость с foundation-термином `workflow binding` сохраняется: binding трактуется как optional metadata hint для compiler, а не как отдельный runtime execution-template;
  - `PoolExecutionPlan` компилируется детерминированно из run-контекста (`pool`, период, направление, template version, source hash) в workflow-compatible graph;
  - `Pool Run` создаётся/выполняется через workflow runtime с сохранением pool-доменной идентичности.
- Зафиксировать явный approval gate для `safe` режима:
  - `safe`: создаётся `workflow_run` с `approval_required=true` и явной фазой `approval_state=preparing`; pre-publish шаги (`prepare_input`, `distribution_calculation`, `reconciliation_report`) выполняются до ожидания решения оператора, после чего run переходит в `approval_state=awaiting_approval`; `publication_odata` не enqueue до явной команды подтверждения;
  - `unsafe`: `approval_state=not_required`, подтверждение (`approved_at`) проставляется автоматически при старте run;
  - команда подтверждения/остановки публикации выносится в явный API-контракт (`confirm-publication` / `abort-publication`).
- Зафиксировать канонический mapping статусов (без open-ended интерпретаций):
  - `pool:draft` — локально создан run до создания `workflow_run`;
  - `workflow:(pending|running) + approval_required=true + approved_at is null + approval_state=preparing -> pool:validated` (`status_reason=preparing`);
  - `workflow:pending + approval_required=true + approved_at is null + approval_state=awaiting_approval -> pool:validated` (`status_reason=awaiting_approval`);
  - `workflow:pending + (approval_required=false OR approved_at is not null) -> pool:validated` (`status_reason=queued`);
  - `workflow:running + (approval_required=false OR approved_at is not null) -> pool:publishing`;
  - `workflow:completed + failed_targets=0 -> pool:published`;
  - `workflow:completed + failed_targets>0 -> pool:partial_success`;
  - `workflow:failed|cancelled -> pool:failed`.
- Зафиксировать tenant boundary для unified runtime:
  - `WorkflowExecution` получает `tenant_id` и `execution_consumer`;
  - для `execution_consumer=pools` `tenant_id` обязателен;
  - `PoolRun.tenant_id` и `WorkflowExecution.tenant_id` обязаны совпадать;
  - создание/чтение workflow-run вне tenant-контекста pool-run запрещено.
- Зафиксировать единую retry-семантику для публикации:
  - доменный контракт `max_attempts_total=5` (включая initial attempt), совместимый с foundation формулировкой `max_attempts=5`;
  - `retry_interval_seconds` конфигурируем, но эффективный интервал не может превышать 120 секунд;
  - компилятор маппит это в workflow step policy (initial attempt + bounded retries);
  - endpoint retry на facade повторно исполняет только failed subset через workflow runtime.
- Зафиксировать queueing-контракт phase 1:
  - используется существующий workflow stream `commands:worker:workflows`;
  - приоритет по умолчанию `normal`;
  - для `safe` режима enqueue publication step выполняется только после подтверждения;
  - выделенный SLA/priority lane не вводится в этом change.
- Принять deferred execution scope из `add-intercompany-pool-distribution-module`:
  - фактический старт/исполнение `pool run`,
  - lifecycle orchestration и status projection,
  - unified provenance/diagnostics,
  - единая retry/audit semantics через workflow core.
- Сохранить publication service (OData) как adapter-слой step execution, а не как отдельный оркестратор, и зафиксировать контракт identity/diagnostics:
  - strategy-based resolver внешнего document identity (`_IDRRef|Ref_Key` primary, `ExternalRunKey` fallback);
  - канонический набор полей диагностики публикации (target database, payload summary, http/transport error, domain error code/message, attempt number, timestamp).
- Ввести совместимый API переход:
  - `/pools/runs*` остаётся доменным API,
  - но фактическое исполнение и статусная модель резолвятся через workflow run reference;
  - API обязан возвращать provenance block (`workflow_run_id`, `workflow_status`, `approval_state`, `terminal_reason`, `execution_backend`, `retry_chain`) как для unified, так и для legacy исторических run (с оговорённой nullable-семантикой), где `workflow_run_id` = root execution chain, а текущая попытка определяется через `retry_chain`;
  - для historical run допускается optional `legacy_reference`, если он доступен в источнике данных.
- Зафиксировать явный API-контракт safe-команд:
  - `POST /api/v2/pools/runs/{run_id}/confirm-publication`;
  - `POST /api/v2/pools/runs/{run_id}/abort-publication`;
  - команды применимы только к safe-run (`approval_required=true`); для `unsafe` возвращается business conflict;
  - семантическая идемпотентность команд означает отсутствие изменения состояния при повторе и запрет duplicate enqueue; response class детерминирован state-matrix (`202`/`200`/`409`);
  - `confirm-publication` допустим только из `approval_state=awaiting_approval`: первый вызов возвращает `202 Accepted` (enqueue publication), повтор в facade-состояниях `validated/queued` или `publishing` возвращает `200 OK` idempotent no-op;
  - `abort-publication` допустим только до старта шага `publication_odata`: первый вызов возвращает `202 Accepted` (cancel execution), повторный `abort-publication` для run c `terminal_reason=aborted_by_operator` возвращает `200 OK` idempotent no-op;
  - `abort-publication` после старта `publication_odata` всегда возвращает business conflict.
- Зафиксировать канонический error payload для `409 Conflict` на safe-командах:
  - `error_code`,
  - `error_message`,
  - `conflict_reason` (`not_safe_run|awaiting_pre_publish|publication_started|terminal_state|cross_tenant`),
  - `retryable`,
  - `run_id`.
- Зафиксировать contract source-of-truth для `approval_state`:
  - `approval_state` хранится в workflow execution metadata как каноническое runtime-поле;
  - `GET /api/v2/pools/runs/{run_id}` возвращает `approval_state` для unified execution (`nullable` для legacy run).
- Зафиксировать единый source-of-truth: execution-runtime семантика `pool-distribution-runs` и `pool-odata-publication` резолвится этим change, а `add-intercompany-pool-distribution-module` остаётся источником domain vocabulary/foundation.
- Зафиксировать anti-drift архитектурные инварианты change:
  - `approval_required=true` и `approved_at is null` НЕ может проецироваться в `pool:publishing`;
  - `status_reason` допустим только для `pool:validated`;
  - `abort-publication` после старта `publication_odata` всегда `business conflict`;
  - state-matrix `confirm/abort` обязателен и не допускает implicit интерпретаций;
  - изменения runtime-семантики считаются валидными только при синхронном обновлении `proposal.md`, `design.md`, `tasks.md` и `specs/pool-workflow-execution-core/spec.md`.
- Запретить удаление `workflows` до миграции всех consumers на unified execution core.
- Зафиксировать де-комиссию `workflows` только через preflight с реестром consumers и критерием готовности миграции.

## Impact
- Affected specs:
  - `pool-workflow-execution-core` (execution source-of-truth)
  - `pool-distribution-runs` (domain vocabulary; runtime semantics ссылаются на execution source-of-truth)
  - `pool-odata-publication` (domain publication contract; runtime semantics ссылаются на execution source-of-truth)
- Prerequisites:
  - foundation задачи из `add-intercompany-pool-distribution-module` (catalog/data/contracts/UI baseline) должны быть завершены или зафиксированы как входной baseline.
  - OData compatibility profile зафиксирован как source-of-truth артефакт `openspec/changes/refactor-unify-pools-workflow-execution-core/odata-compatibility-profile.md`; production rollout unified publication запрещён при отсутствии утверждённого profile entry для целевой конфигурации и без фиксации `profile_version` в release-артефакте.
- Affected code (high-level):
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/templates/workflow/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `contracts/orchestrator/**`
  - `frontend/src/pages/Pools/**`

## Non-Goals
- Полное удаление `workflows` в рамках этого change.
- Переписывание business-алгоритмов распределения (top-down/bottom-up) как предметной логики.
- Замена OData-интеграции на другой транспорт.
- Введение отдельной queue/lane инфраструктуры для pools в phase 1.
