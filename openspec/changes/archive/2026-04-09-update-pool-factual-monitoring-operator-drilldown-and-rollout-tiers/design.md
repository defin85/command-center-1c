## Context

Текущая factual monitoring реализация уже включает:
- отдельный workspace `/pools/factual`;
- materialized projection и batch settlement statuses;
- manual review queue;
- carry-forward backend path;
- active sync freshness target `120s`;
- nightly reconcile для closed quarter.

Review показал два остаточных разрыва:
- operator surface не выводит полную картину `incoming/outgoing/open_balance` и carry-forward lineage, хотя backend payload эти данные уже содержит;
- у обычного оператора нет shipped refresh/retry control для factual sync в контексте конкретного `pool + quarter`, есть только implicit GET refresh и internal/debug trigger paths;
- rollout tiers `active / warm / cold` описаны в helpers и тестах, но runtime практически использует только `active` плюс closed-quarter reconcile.

## Goals / Non-Goals

- Goals:
  - довести factual workspace до полного operator drill-down без raw JSON inspection;
  - дать оператору shipped refresh/retry path внутри factual workspace;
  - сделать `warm` tier реальным runtime behavior, а не только helper/test contract;
  - сохранить текущие runtime boundaries и не ломать active 120-second path.
- Non-Goals:
  - не менять source profile `sales_report_v1`;
  - не вводить новый worker service или новый frontend app;
  - не пересматривать settlement statuses или review action vocabulary.

## Decisions

### 1. Operator surface reuse'ит уже существующий payload, а не изобретает новый API

Backend уже сериализует `outgoing_amount` для settlement/edge и carry-forward metadata в `settlement.summary`. Новый change должен в первую очередь довести rendering/UX этих полей в factual workspace и закрыть test coverage. Новый primary endpoint для этого не требуется, если существующий payload остаётся достаточным.

### 2. Operator refresh path должен быть shipped UI control, а не debug-only practice

Сейчас фактический rerun achievable через workspace GET и internal/debug triggers, но это не operator-grade UX. Новый change должен добавить явное operator-facing действие в factual workspace для конкретного `pool + quarter`, которое запускает тот же bounded refresh contract безопасным способом внутри существующих runtime boundaries.

Такой control surface не должен превращаться в generic scheduler console или требовать знания internal endpoints. Пользователь работает только с factual workspace route и получает явный feedback о pending/running/error state.

### 3. Rollout tiers становятся общим orchestrator decision, а не набором несвязанных helper constants

Выбор `active / warm / cold` должен происходить на canonical orchestrator path и затем попадать в workflow contract/metadata. Workspace-triggered sync может продолжать форсировать `active` для текущего operator request, но scheduler-managed path обязан уметь детерминированно выдавать `warm` для non-active, но ещё operationally relevant quarter contexts.

### 4. Existing scheduler tick остаётся базовой точкой входа

Change не требует нового top-level runtime. Допустимо сохранить существующий scheduler tick и nightly reconcile job, если orchestrator-side candidate selection + checkpoint gating начнут реально использовать `warm` interval. Отдельный новый cron/job нужен только если без него нельзя обеспечить чёткий runtime contract.

## Risks / Trade-offs

- Если classifier будет слишком завязан на ephemeral UI activity, runtime станет недетерминированным.
  - Mitigation: использовать устойчивые доменные сигналы quarter/status/backlog/review/open balance, а workspace-open path считать явным override только для конкретного request-triggered sync.
- Если operator refresh будет реализован как raw force rerun без guardrails, пользователь сможет перегружать factual lane.
  - Mitigation: reuse существующего checkpoint/idempotency gating и показывать operator'у pending/running state вместо бесконтрольного enqueue.
- Если operator surface начнёт выводить carry-forward слишком сыро, detail pane превратится в debug JSON.
  - Mitigation: показывать human-readable linkage и quarter context через platform primitives, а не raw metadata dump как primary path.

## Migration Plan

1. Расширить operator detail rendering и shipped refresh control поверх текущего workspace payload/runtime path.
2. Ввести canonical activity classifier и провести его через scheduler/workflow contract.
3. Обновить runtime/tests/observability assertions.
4. Прогнать targeted validation и strict OpenSpec validation.
