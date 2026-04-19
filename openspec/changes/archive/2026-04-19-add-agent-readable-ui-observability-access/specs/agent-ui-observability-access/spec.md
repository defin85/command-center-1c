## ADDED Requirements

### Requirement: Система MUST предоставлять agent-readable UI observability path для dev и prod

Система ДОЛЖНА (SHALL) предоставлять canonical agent-readable access path для диагностики UI инцидентов как минимум на двух контурах:
- `dev/local` через export текущего browser session bundle;
- `prod` через authenticated read-only diagnostics/query surface.

Оба path ДОЛЖНЫ (SHALL) возвращать machine-readable данные, достаточные для анализа UI проблемы без необходимости screen scraping product UI или прямого ручного доступа к browser console.

#### Scenario: Агент получает bundle воспроизведённой dev-проблемы
- **GIVEN** инженер воспроизвёл UI проблему на локальном или dev runtime
- **WHEN** агент использует repository-defined debug/export path
- **THEN** он получает machine-readable bundle текущего UI observability context
- **AND** bundle пригоден для последующего автоматического анализа без ручного copy/paste из browser console

#### Scenario: Агент читает recent UI incidents на prod
- **GIVEN** в production накопились recent UI failures или correlated problem details
- **WHEN** агент использует canonical read-only diagnostics surface
- **THEN** он получает redacted machine-readable summaries по этим инцидентам
- **AND** surface не требует прямого доступа к живому пользовательскому браузеру

### Requirement: Machine-readable traces/errors/actions MUST быть достаточным minimal contract для default agent monitoring path

Система ДОЛЖНА (SHALL) считать достаточным minimal contract для default agent monitoring path следующий набор сигналов:
- semantic UI action events;
- route/session/release/build metadata;
- runtime/render/network error events;
- correlated identifiers `trace_id`, `request_id`, `ui_action_id`;
- canonical backend trace lookup metadata.

Visual replay, DOM/session recording и video-like playback НЕ ДОЛЖНЫ (SHALL NOT) быть обязательным условием для работы default agent monitoring path.

#### Scenario: UI incident diagnosable без replay
- **GIVEN** агент анализирует ошибку operator-facing route
- **WHEN** у него есть machine-readable traces/errors/actions и correlated identifiers
- **THEN** он может связать UI symptom с route/action/runtime context и backend trace
- **AND** отсутствие session replay не блокирует базовую диагностику инцидента

### Requirement: Prod agent monitoring path MUST быть redaction-first и RBAC-protected

Система ДОЛЖНА (SHALL) защищать production agent monitoring path через:
- explicit RBAC/authorization;
- redaction policy;
- bounded retention;
- sampling policy для volume-heavy telemetry.

Prod path НЕ ДОЛЖЕН (SHALL NOT) раскрывать raw secrets, cookies, auth headers, raw bodies, password-like поля или не-redacted user input fragments.

#### Scenario: Неавторизованный actor не получает prod UI telemetry
- **GIVEN** actor без требуемых прав пытается читать production UI observability surface
- **WHEN** он вызывает canonical query path
- **THEN** система fail-close'ится с authorization error
- **AND** никаких redacted или raw incident details не возвращается

#### Scenario: Production incident summary не раскрывает чувствительные данные
- **GIVEN** в prod произошёл UI инцидент на route с form input и auth context
- **WHEN** агент читает machine-readable incident summary
- **THEN** он видит только redacted metadata и correlation fields
- **AND** raw sensitive значения отсутствуют

### Requirement: UI incident MUST быть связываем с backend diagnostics без screen scraping observability UI

Система ДОЛЖНА (SHALL) предоставлять canonical machine-readable linkage от UI incident к backend diagnostics, чтобы агент мог перейти от UI signal к correlated server-side trace или problem details без screen scraping Jaeger/Grafana UI как primary path.

#### Scenario: Агент находит backend trace по UI incident summary
- **GIVEN** агент получил machine-readable UI incident summary
- **WHEN** summary содержит `trace_id` или эквивалентный correlation contract
- **THEN** агент может получить correlated backend diagnostics через canonical query path
- **AND** ему не требуется парсить vendor-specific observability web UI как основной механизм
