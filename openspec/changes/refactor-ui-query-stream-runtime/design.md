## Context
Текущий runtime слой frontend вырос вокруг React Query defaults и database SSE singleton без явного разделения ответственности.

Наблюдаемое поведение в коде:
- глобальный `QueryClient` задаёт одинаковые `retry: 2`, `refetchOnWindowFocus: true`, `refetchOnReconnect: true` для всех query workloads;
- `MainLayout` и `AuthzProvider` поднимают несколько bootstrap/capability запросов параллельно;
- `DatabaseStreamContext` включает stream по факту staff-сессии, а `databaseStreamManager` на штатном пути запрашивает ticket с `force=true`;
- `databaseStreamManager` инвалидирует database cache даже на `onOpen`, без domain event;
- `/decisions` сначала поднимает database list, потом metadata-management, затем decisions collection с дополнительной логикой unscoped fallback;
- `/pools/binding-profiles` eager грузит `listOrganizationPools()` на route mount, даже когда usage-секция пользователю ещё не нужна.

Это создаёт request amplification и делает default path чувствительным к любому новому data-heavy surface.

## Goals / Non-Goals
- Goals:
  - Разделить runtime на явные слои: query policy, bootstrap read-model, realtime coordination, event projection, UX error policy.
  - Сделать один database stream owner на браузер и убрать cross-tab takeover как нормальный путь.
  - Перенести freshness модели от blanket refetch к event-driven invalidation и explicit refresh.
  - Зафиксировать default-path request budget для `/decisions` и `/pools/binding-profiles`.
  - Сохранить contract-first подход для stream endpoints и frontend clients.
- Non-Goals:
  - Заменять весь frontend state management на другой framework.
  - Переписывать все existing React Query hooks в один проход без приоритизации.
  - Делать gateway rate-limit мягче вместо исправления архитектуры клиента и stream ownership.

## Drivers
- Надёжность default staff path под gateway limit `100 req/min`.
- Отсутствие duplicate error flood в UI.
- Детерминированное multi-tab и multi-browser поведение.
- Низкая цена сопровождения для новых admin surfaces после `refactor-ui-platform-on-ant`.
- Явная `Requirement -> Code -> Test` трассировка для runtime non-functional behavior.

## Decision
Выбрать layered runtime architecture, а не серию page-local hotfixes.

### 1. Query policy registry вместо глобального one-size-fits-all default
React Query должен использовать несколько явных профилей:
- `bootstrap`: без blind retry на `429/4xx`, без focus refetch, с предсказуемым stale window;
- `interactive`: допускает controlled retry для network/5xx и explicit invalidation после пользовательского действия;
- `background`: silent/deduped error semantics, без focus storm;
- `realtime-backed`: freshness идёт через stream projector, а не через window-focus refetch;
- `capability`: короткоживущий compatibility profile только там, где bootstrap read-model ещё не мигрирован.

Это фиксирует root cause, а не только симптомы на двух страницах.

### 2. Shell bootstrap должен стать единым read-model
`me`, tenant context, access summary и UI capability flags должны приходить через один canonical bootstrap contract.

Причины:
- shell queries описывают один и тот же operator session context;
- несколько capability probes создают ненужный request burst и сложный partial-failure UX;
- единый bootstrap response проще кэшировать, инвалидировать и тестировать.

До полной миграции допускается временный compatibility layer, но spec contract должен считать bootstrap resource primary path.

### 3. Realtime coordination делится на transport, coordinator и projector
Текущий singleton смешивает всё сразу. Нужны три отдельных слоя:
- `transport`: открывает/закрывает SSE, ничего не знает про React Query;
- `browser coordinator`: выбирает stream owner, координирует tabs через `BroadcastChannel`/эквивалент и решает reconnect policy;
- `event projector`: переводит domain events в точечные cache updates/invalidation по known query keys.

`onOpen` stream НЕ должен инвалидировать кэш сам по себе. Invalidation допустим только по фактическому domain event или по явному operator refresh.

### 4. Browser-scoped ownership, backend-scoped client session
Нормальный путь должен быть таким:
- один browser instance имеет один `client_instance_id`;
- только leader-tab держит database stream transport;
- follower tabs получают session state и invalidation events через browser coordination;
- backend lease/scoping строится хотя бы по `(user_id, client_instance_id, cluster_scope)`, а не только по `user_id`;
- default connect не использует silent takeover;
- explicit recovery/takeover остаётся отдельным ручным path.

Это закрывает сразу два класса проблем: cross-tab self-eviction и multi-browser silent conflicts.

### 5. Route budgets фиксируются как часть runtime design, а не как случайные page fixes
Для этого change нужны явные acceptance budgets:
- `/decisions`: initial list load не должен делать unscoped+scoped двойной fetch без необходимости;
- `/pools/binding-profiles`: usage/read of organization pools не должен стартовать, пока пользователь не открыл контекст, где он реально нужен;
- background shell queries не должны сами по себе умножать mount-time burst.

## Alternatives Considered

### Вариант A: Подкрутить только `retry` и `refetchOnWindowFocus`
Плюсы:
- быстро;
- низкий объём правок.

Минусы:
- не решает ownership model для stream;
- не убирает shell capability probes;
- не даёт стабильный multi-tab contract;
- не фиксирует blanket invalidation anti-pattern.

Итог: недостаточно.

### Вариант B: Оставить backend user-wide stream lease и чинить только frontend tabs
Плюсы:
- меньше backend изменений.

Минусы:
- разные браузеры/устройства одного пользователя продолжают конфликтовать;
- `force`/takeover semantics остаются хрупкими;
- observability session conflicts остаётся двусмысленной.

Итог: годится как промежуточная фаза, но не как final architecture для этого change.

### Вариант C: Полностью уйти с SSE на WebSocket
Плюсы:
- единый long-lived transport.

Минусы:
- меняет transport foundation шире нужного;
- выходит за scope текущей проблемы;
- требует отдельного design/change по backend delivery model.

Итог: вне scope.

## Proposed Architecture

### Frontend modules
- `queryPolicies/*`: профили retry/refetch/error semantics.
- `sessionBootstrap/*`: единый bootstrap query и provider.
- `realtime/databaseStreamTransport/*`: чистый SSE client adapter.
- `realtime/databaseStreamCoordinator/*`: leader election, ownership state, cooldown/reconnect policy.
- `realtime/databaseEventProjector/*`: mapping `DatabaseStreamEvent -> queryKey actions`.
- `errors/apiErrorPolicy/*`: dedupe, background-vs-primary classification, page/global handoff rules.

### Backend/session contract
- `stream-ticket` принимает `client_instance_id` и возвращает session/lease metadata.
- `stream` валидирует lease/session и поддерживает conservative reconnect/resume path.
- `force`/takeover не является default-path поведением.
- conflict response остаётся fail-closed, но содержит machine-readable `retry_after` и ownership diagnostics.

### Observability
- Счётчики/метрики минимум для:
  - active database stream sessions;
  - stream conflicts/takeovers;
  - reconnect loops;
  - suppressed duplicate background errors;
  - request budget per route mount в browser smoke/diagnostic tooling.

## Migration / Sequencing
1. Зафиксировать spec contract и acceptance budgets.
2. Ввести query profiles и error policy, не ломая текущие routes.
3. Ввести shell bootstrap read-model.
4. Перестроить database realtime coordinator и backend session contract.
5. Мигрировать `/decisions` и `/pools/binding-profiles` на новый runtime path.
6. Добавить multi-tab smoke и runbook/diagnostics.

## Risks / Trade-offs
- Change затрагивает frontend runtime и backend contract одновременно.
  - Mitigation: staged implementation с явными compatibility boundaries и контрактными тестами.
- Cross-tab coordination зависит от browser APIs.
  - Mitigation: зафиксировать supported runtime contract и explicit fallback policy как часть implementation design, а не молчаливое degrade.
- Bootstrap aggregation может расширить один payload.
  - Mitigation: держать bootstrap focused на shell/session data и не превращать его в giant everything endpoint.
- Точечный event projector потребует richer domain event mapping.
  - Mitigation: сначала ввести conservative event-to-query map, затем расширять granularity без blanket invalidation rollback.
