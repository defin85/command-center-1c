## ADDED Requirements
### Requirement: OData credentials transport and auth encoding MUST сохранять Unicode без потерь
Система ДОЛЖНА (SHALL) для publication path передавать `username/password`, полученные из orchestrator credentials transport, без lossy преобразований (normalization/transliteration/truncation).

Worker OData client ДОЛЖЕН (SHALL) формировать HTTP Basic credentials так, чтобы Unicode символы (включая кириллицу) в `username/password` кодировались в UTF-8 октеты перед Base64.

Это требование ДОЛЖНО (SHALL) одинаково применяться к `actor` и `service` auth strategy.

#### Scenario: Actor credentials с кириллицей доходят до OData Authorization header
- **GIVEN** publication flow использует `actor` strategy и orchestrator вернул credentials с кириллическими символами
- **WHEN** worker выполняет OData HTTP-запрос
- **THEN** `Authorization: Basic ...` соответствует Base64 от UTF-8 строки `username:password`
- **AND** запрос не отклоняется локально из-за client-side encoding ошибок

#### Scenario: Service credentials с кириллицей поддерживаются без изменения fail-closed semantics
- **GIVEN** publication flow использует `service` strategy с кириллическими credentials
- **WHEN** worker запрашивает и использует credentials для OData transport
- **THEN** credentials передаются без потери символов
- **AND** при `401/403` система сохраняет fail-closed classification как credentials/configuration error

#### Scenario: ASCII credentials сохраняют backward compatibility
- **GIVEN** publication flow использует ASCII credentials
- **WHEN** worker формирует Authorization header
- **THEN** формат и поведение запроса совпадают с текущим контрактом
- **AND** existing retry/error semantics не меняются
