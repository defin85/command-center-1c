## ADDED Requirements
### Requirement: OData verification MUST поддерживать UTF-8 Basic auth для document-by-ref проверки
Система верификации публикации MUST получать документы из OData по published refs с использованием UTF-8 кодирования credentials в Basic Authorization header.

#### Scenario: Кириллические учетные данные не ломают verification transport
- **GIVEN** target infobase использует логин/пароль с non-latin символами
- **WHEN** verifier выполняет запрос `$metadata` и чтение опубликованных документов
- **THEN** transport использует UTF-8 Basic Authorization
- **AND** проверка не падает из-за `latin-1` кодирования

### Requirement: OData verification MUST проверять полноту опубликованных документов по completeness profile
Verifier MUST сравнивать фактически опубликованные документы с completeness profile: обязательные реквизиты и обязательные табличные части с минимальным числом строк.

#### Scenario: Отсутствующая табличная часть фиксируется как mismatch
- **GIVEN** published ref указывает на документ без обязательной строки табличной части
- **WHEN** verifier выполняет проверку по profile
- **THEN** формируется machine-readable mismatch с указанием `entity_name`, `field_or_table_path` и `database_id`
- **AND** run verification status устанавливается в failed
