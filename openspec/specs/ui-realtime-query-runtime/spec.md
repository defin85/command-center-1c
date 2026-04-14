# ui-realtime-query-runtime Specification

## Purpose
TBD - created by archiving change refactor-ui-query-stream-runtime. Update Purpose after archive.
## Requirements
### Requirement: Frontend query runtime MUST использовать workload-aware policies вместо одного глобального retry/refetch default
Система ДОЛЖНА (SHALL) классифицировать frontend query workloads минимум на `bootstrap`, `interactive`, `background`, `realtime-backed` и `capability` и применять к ним разные retry/refetch/error semantics.

Для default admin path:
- `429` и прочие deterministic `4xx` ошибки НЕ ДОЛЖНЫ (SHALL NOT) бесконечно или слепо ретраиться как обычные transient failures;
- background и shell queries НЕ ДОЛЖНЫ (SHALL NOT) автоматически refetch'иться только из-за window focus/reconnect, если их freshness уже обеспечивается bootstrap contract или realtime invalidation;
- interactive refresh/update path МОЖЕТ (MAY) выполнять explicit invalidation/refetch после пользовательского действия.

#### Scenario: Background query не разгоняет rate-limit повторными retry
- **GIVEN** staff-пользователь открывает data-heavy admin route
- **AND** один из background query получает HTTP `429`
- **WHEN** runtime обрабатывает ошибку
- **THEN** query НЕ ДОЛЖЕН автоматически повторяться по generic retry policy, предназначенной для network/5xx ошибок
- **AND** система сохраняет контролируемое fail-closed состояние без request storm

#### Scenario: Focus не вызывает повторный shell/bootstrap storm
- **GIVEN** shell bootstrap и background capability data уже загружены
- **WHEN** окно браузера теряет и возвращает фокус
- **THEN** runtime НЕ ДОЛЖЕН автоматически рефетчить эти данные только по факту focus
- **AND** freshness остаётся под контролем bootstrap invalidation или явного refresh path

### Requirement: App shell MUST использовать единый bootstrap read-model вместо capability probe-запросов как primary path

Система ДОЛЖНА (SHALL) предоставлять canonical bootstrap/read-model resource для shell session context, включающий как минимум:
- user identity summary;
- tenant context summary;
- access summary, необходимый для shell gating;
- UI capability flags, нужные для route/menu composition;
- i18n summary, включающий `supported_locales`, `default_locale`, `effective_locale` и optional `requested_locale`.

`MainLayout`, `AuthzProvider` и другие shell-level consumers НЕ ДОЛЖНЫ (SHALL NOT) на default path определять capability или locale доступность через набор независимых probe API calls, если тот же context доступен через bootstrap resource.

#### Scenario: Staff route загружает shell context и locale через один bootstrap contract

- **GIVEN** авторизованный staff-пользователь открывает `/decisions`
- **WHEN** frontend инициализирует shell/runtime context
- **THEN** `me`, tenant/access summary, shell capability flags и locale summary приходят через один canonical bootstrap path
- **AND** shell не делает отдельные capability или locale probe calls только для построения меню и глобальных guard'ов

#### Scenario: Bootstrap locale failure даёт стабильный shell error state

- **GIVEN** bootstrap resource не может вернуть обязательный shell context, включая locale summary
- **WHEN** shell не может собрать обязательный runtime context
- **THEN** пользователь видит один стабильный shell-level failure state
- **AND** система НЕ ДОЛЖНА запускать cascade из secondary locale probe errors как substitute path

### Requirement: Realtime invalidation MUST быть event-driven и scoped по query keys
Система ДОЛЖНА (SHALL) проецировать database realtime events в явные действия над cache/query слоями.

Stream open, reconnect или heartbeat сами по себе НЕ ДОЛЖНЫ (SHALL NOT) вызывать blanket cache invalidation. Cache updates/invalidation допустимы только:
- по фактическому domain event;
- по явному operator refresh;
- по documented recovery path после подтверждённой потери консистентности.

#### Scenario: Stream open не инвалидирует queries без domain event
- **GIVEN** database stream успешно подключился или переподключился
- **WHEN** ещё не получено ни одного domain event
- **THEN** runtime НЕ ДОЛЖЕН инвалидировать database-related query cache только из-за `onOpen`

#### Scenario: Domain event инвалидирует только связанный query scope
- **GIVEN** stream прислал событие изменения database metadata
- **WHEN** event projector обрабатывает это событие
- **THEN** invalidation/update применяется только к связанным database query keys и их documented consumers
- **AND** unrelated route caches не инвалидируются blanket-способом

### Requirement: Background transport errors MUST быть дедуплицированы и отделены от page-level data failures
Система ДОЛЖНА (SHALL) различать primary route data failure и repeated background transport errors.

Repeated background `429`/transport errors НЕ ДОЛЖНЫ (SHALL NOT) создавать toast flood. Page-level data loader ДОЛЖЕН (SHALL) по-прежнему показывать устойчивое error state там, где пользователь реально потерял данные текущего surface.

#### Scenario: Повторный `429` не превращается в пачку одинаковых уведомлений
- **GIVEN** один и тот же background request несколько раз подряд получает `429`
- **WHEN** global error policy обрабатывает эти ошибки
- **THEN** пользователь получает не более одного дедуплицированного глобального уведомления на этот error class/window
- **AND** последующие повторы не создают новый toast flood

#### Scenario: Route-level failure остаётся видимым без глобального шума
- **GIVEN** `/pools/binding-profiles` не смог загрузить primary list data
- **WHEN** background dedupe policy активна
- **THEN** страница всё равно показывает устойчивый route-level error state
- **AND** global background dedupe не скрывает потерю primary route data

### Requirement: Heavy admin routes MUST избегать mount-time waterfalls и eager secondary reads на default path
Система ДОЛЖНА (SHALL) проектировать data-heavy admin routes так, чтобы primary data path был минимальным и детерминированным, а expensive secondary reads загружались только при реальной необходимости.

#### Scenario: `/decisions` не делает лишний unscoped/scoped waterfall при первичной загрузке
- **GIVEN** пользователь открывает `/decisions`
- **WHEN** runtime определяет effective database selection и metadata read policy
- **THEN** primary decisions collection читается один раз по корректному scope для этого состояния
- **AND** route НЕ ДОЛЖЕН выполнять лишнюю пару `unscoped -> scoped` reads как штатный initial path

#### Scenario: `/pools/binding-profiles` usage data не загружается eager на mount
- **GIVEN** пользователь открывает `/pools/binding-profiles`
- **WHEN** список профилей уже загружен, но usage/detail section ещё не нужен
- **THEN** expensive usage read для organization pools НЕ ДОЛЖЕН стартовать автоматически только из-за route mount
- **AND** этот read выполняется только когда пользователь действительно открыл контекст, где usage нужен

