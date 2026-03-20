## 1. Спецификация и контракт runtime
- [x] 1.1 Зафиксировать capability `ui-realtime-query-runtime` для query policies, shell bootstrap, event-driven invalidation и background error policy.
- [x] 1.2 Зафиксировать capability `database-realtime-streaming` для stream ownership/session semantics, explicit recovery и multi-tab/browser coordination contract.
- [x] 1.3 Зафиксировать request-budget expectations для `/decisions` и `/pools/binding-profiles` как acceptance path этого change.

## 2. Frontend runtime decomposition
- [x] 2.1 Выделить query policy registry с отдельными профилями минимум для `bootstrap`, `interactive`, `background`, `realtime-backed`, `capability`.
- [x] 2.2 Разделить текущий database stream singleton на transport, browser coordinator и event projector без blanket cache invalidation на `onOpen`.
- [x] 2.3 Ввести cross-tab coordination (`leader`/`followers`) так, чтобы один браузер держал один stream owner path.
- [x] 2.4 Ввести dedupe/classification policy для repeated background `429`/transport errors и убрать toast flood как default UX.

## 3. Shell bootstrap и route budget
- [x] 3.1 Заменить shell capability probes единым bootstrap/read-model path для `me`, tenant context, access summary и UI capability flags.
- [x] 3.2 Перестроить `/decisions` так, чтобы initial collection read не делал лишний unscoped/scoped waterfall при выборе effective database.
- [x] 3.3 Перестроить `/pools/binding-profiles` так, чтобы heavy usage read не стартовал eager на route mount и загружался только при реальной необходимости.

## 4. Backend/session contract
- [x] 4.1 Обновить `/api/v2/databases/stream-ticket/` и `/api/v2/databases/stream/` до client-session/lease semantics вместо implicit user-wide takeover по умолчанию.
- [x] 4.2 Зафиксировать explicit recovery/takeover path, `retry_after`/ownership metadata и observability hooks для stream conflicts.
- [x] 4.3 Обновить OpenAPI/contracts/generated frontend types и checked-in docs/runbook примеры под новый runtime contract.

## 5. Проверки и выпуск
- [x] 5.1 Добавить unit/integration tests для query profiles, error dedupe, event projector и browser coordinator.
- [x] 5.2 Добавить browser smoke для single-tab и multi-tab scenarios на `/decisions` и `/pools/binding-profiles`, подтверждающий отсутствие `429` storm и duplicate notifications на default path.
- [x] 5.3 Прогнать релевантные frontend/backend quality gates и `openspec validate refactor-ui-query-stream-runtime --strict --no-interactive`.
