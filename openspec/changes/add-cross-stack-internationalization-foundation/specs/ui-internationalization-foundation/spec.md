## ADDED Requirements

### Requirement: Shell MUST resolve and expose effective operator locale through one canonical context

Система ДОЛЖНА (SHALL) поддерживать как минимум locale `ru` и `en` для operator-facing shell и platform-governed frontend surfaces.

Система ДОЛЖНА (SHALL) использовать BCP 47 language tags как canonical public locale identifiers на frontend/API boundary.

Система ДОЛЖНА (SHALL) вычислять effective locale в следующем порядке:
1. явный SPA override, сохранённый для текущего operator context и отправленный в API через `X-CC1C-Locale`;
2. поддерживаемый browser/request language signal;
3. deployment default locale.

Shell bootstrap ДОЛЖЕН (SHALL) возвращать `i18n` summary как canonical read-model для:
- `supported_locales`;
- `default_locale`;
- `requested_locale`, если явный override присутствует;
- `effective_locale`.

#### Scenario: Explicit operator selection overrides browser locale

- **GIVEN** браузер пользователя предпочитает `ru`
- **AND** оператор явно переключил язык shell на `en`
- **WHEN** SPA выполняет authenticated bootstrap request
- **THEN** запрос передаёт `X-CC1C-Locale: en`
- **AND** bootstrap возвращает `requested_locale = "en"`
- **AND** bootstrap возвращает `effective_locale = "en"`

#### Scenario: Unsupported browser locale falls back to deployment default

- **GIVEN** пользователь открывает приложение без явного locale override
- **AND** browser signal указывает на неподдерживаемый locale
- **WHEN** shell инициализирует locale context
- **THEN** система использует deployment default locale
- **AND** bootstrap отражает этот fallback в `effective_locale`

### Requirement: Frontend MUST use one centralized translation runtime with namespaces and fallback

Система ДОЛЖНА (SHALL) предоставлять один shared frontend i18n runtime для operator-facing copy, доступный из shell, platform primitives и governed route surfaces.

Этот runtime ДОЛЖЕН (SHALL) поддерживать:
- namespace-based catalogs;
- lazy loading route/domain namespaces;
- fallback to common/shared namespace and fallback locale;
- typed or otherwise statically verifiable translation key usage на canonical frontend path.

Новые или materially rewritten platform-governed surfaces НЕ ДОЛЖНЫ (SHALL NOT) вводить самостоятельные route-local copy registries как primary path вместо canonical i18n runtime.

#### Scenario: Lazy route loads its own namespace without duplicating shell catalogs

- **GIVEN** governed route использует domain-specific copy
- **WHEN** пользователь впервые открывает этот route
- **THEN** route загружает свой namespace через canonical i18n runtime
- **AND** shell/common catalogs не дублируются внутри route module

#### Scenario: Missing route key falls back without crashing the surface

- **GIVEN** route namespace ещё не содержит один из translation keys
- **WHEN** governed surface рендерит этот элемент
- **THEN** runtime использует configured fallback namespace или fallback locale
- **AND** пользователь не получает runtime crash только из-за отсутствующего key

### Requirement: User-visible formatting MUST be derived from the same effective locale as UI copy and vendor locale

Система ДОЛЖНА (SHALL) централизовать formatting для date/time/number/list/relative time и vendor locale wiring в одном locale-aware layer, который использует тот же effective locale, что и translation runtime.

Platform shell ДОЛЖЕН (SHALL) быть canonical owner mapping-а между public locale id и vendor-specific locale packs, включая `antd`.

Platform-governed surfaces НЕ ДОЛЖНЫ (SHALL NOT) использовать raw `toLocaleString()`, `toLocaleDateString()`, `toLocaleTimeString()` или route-local hardcoded locale tags как primary user-facing formatting path вне canonical formatter layer.

#### Scenario: Locale switch updates timestamps and vendor copy consistently

- **GIVEN** пользователь переключает shell locale с `ru` на `en`
- **WHEN** governed route повторно рендерится с тем же data state
- **THEN** даты и числа форматируются для `en`
- **AND** `antd` empty/loading/state copy использует тот же effective locale
- **AND** route не остаётся в mixed state из разных locale owners

### Requirement: SPA problem handling MUST remain code-first while UX copy becomes locale-aware

Публичные API problem/error payloads ДОЛЖНЫ (SHALL) сохранять stable machine-readable `code` или `error_code` как canonical contract для SPA clients.

Frontend ДОЛЖЕН (SHALL) локализовать known error/problem codes через canonical i18n runtime и МОЖЕТ (MAY) показывать raw backend `detail` как secondary diagnostic fallback, если для данного code нет mapped UX copy или требуется дополнительная детализация.

Backend НЕ ДОЛЖЕН (SHALL NOT) делать translated free-text `detail` единственным источником истины для operator-facing SPA behaviour.

#### Scenario: Known problem code renders localized user-facing message

- **GIVEN** API возвращает problem details с `code = "POOL_WORKFLOW_BINDING_REQUIRED"`
- **WHEN** frontend обрабатывает ошибку на governed route
- **THEN** пользователю показывается локализованный message для этого code
- **AND** UI behaviour не зависит от точного текста backend `detail`

#### Scenario: Unknown problem code falls back to generic localized message and diagnostic detail

- **GIVEN** API возвращает неизвестный для frontend `code`
- **WHEN** governed route обрабатывает ошибку
- **THEN** frontend показывает generic localized error message
- **AND** может дополнительно показать raw `detail` как diagnostic context

### Requirement: Request-scoped backend locale MUST be available for server-rendered and admin text without changing async execution semantics

Система ДОЛЖНА (SHALL) делать resolved request locale доступным backend/runtime layer для Django admin, template rendering и других synchronous server-text surfaces.

Система МОЖЕТ (MAY) использовать для этого standard browser language signal, explicit `X-CC1C-Locale`, Django translation context и `LocaleMiddleware` или эквивалентный request-scoped mechanism.

Первый rollout НЕ ДОЛЖЕН (SHALL NOT) автоматически расширять этот контракт на worker-generated business artifacts, long-running exports или доменные payload values без отдельного approved change.

#### Scenario: Admin page honors explicit locale override

- **GIVEN** staff пользователь открывает server-rendered admin surface
- **AND** запрос несёт поддерживаемый explicit locale override
- **WHEN** Django рендерит server-side copy
- **THEN** translation context использует resolved locale этого запроса

#### Scenario: Async execution payload remains semantically unchanged

- **GIVEN** оператор запускает long-running workflow или pool run
- **WHEN** backend обрабатывает execution command
- **THEN** change request locale не меняет business semantics command payload
- **AND** worker-generated domain data не считается автоматически локализованным в рамках этого rollout
