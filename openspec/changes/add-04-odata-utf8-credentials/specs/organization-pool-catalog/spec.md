## MODIFIED Requirements
### Requirement: Metadata catalog auth MUST использовать mapping-only credentials path
Система ДОЛЖНА (SHALL) резолвить credentials для metadata catalog read/refresh только через `InfobaseUserMapping`.

Система НЕ ДОЛЖНА (SHALL NOT) использовать `Database.username/password` как runtime fallback для metadata path.

Система ДОЛЖНА (SHALL) поддерживать Unicode credentials (включая кириллицу) в `ib_username`/`ib_password` и отправлять HTTP Basic credentials в UTF-8 представлении (`username:password` -> UTF-8 octets -> Base64).

Система НЕ ДОЛЖНА (SHALL NOT) отклонять credentials только из-за ограничения `latin-1` в клиентской библиотеке до фактического HTTP-запроса к OData endpoint.

Ошибки auth/configuration ДОЛЖНЫ (SHALL) возвращаться fail-closed с machine-readable кодом и без раскрытия секретов.

#### Scenario: Кириллический service mapping используется в metadata catalog запросе
- **GIVEN** для выбранной ИБ настроен service `InfobaseUserMapping` с `ib_username`/`ib_password`, содержащими кириллические символы
- **WHEN** UI запрашивает metadata catalog или refresh
- **THEN** backend формирует `Authorization: Basic ...` из UTF-8 представления `username:password`
- **AND** запрос к OData endpoint выполняется без локального reject по причине `latin-1 unsupported`

#### Scenario: OData endpoint отклоняет UTF-8 credentials fail-closed ошибкой
- **GIVEN** mapping credentials синтаксически валидны, но фактически отклоняются OData endpoint (401/403)
- **WHEN** backend выполняет metadata catalog fetch
- **THEN** API возвращает fail-closed machine-readable auth/configuration ошибку
- **AND** response не содержит секретов credentials
