# pool-odata-publication Specification

## Purpose
TBD - created by archiving change add-intercompany-pool-distribution-module. Update Purpose after archive.
## Requirements
### Requirement: Publication MUST использовать OData documents + posting flow
Система ДОЛЖНА (SHALL) публиковать результаты run в ИБ через OData на уровне документов 1С и инициировать проведение документа в 1С.

Система НЕ ДОЛЖНА (SHALL NOT) писать итоговые движения напрямую в регистры в рамках базового flow.

#### Scenario: Публикация выполняется через документ и проведение
- **WHEN** run переходит в стадию публикации
- **THEN** система создаёт или обновляет документ через OData
- **AND** запрашивает проведение документа в целевой ИБ

### Requirement: Publication MUST поддерживать partial success и управляемые ретраи
Система ДОЛЖНА (SHALL) поддерживать частично успешную публикацию (`partial_success`) и повторную дозапись failed-частей.

Система ДОЛЖНА (SHALL) поддерживать retry policy с `max_attempts=5` и настраиваемым интервалом повторов (дефолтный потолок 120 секунд).

В рамках этого change retry policy фиксируется как доменный контракт; execution-реализация ретраев и статусной проекции переносится в unified runtime change.

#### Scenario: Неуспешная публикация дозаписывается ретраями
- **GIVEN** публикация в части ИБ завершилась ошибкой
- **WHEN** запускается retry policy
- **THEN** система выполняет повторные попытки только для failed-целей
- **AND** успешные цели не дублируются

### Requirement: External document identity MUST обеспечивать идемпотентный upsert
Система ДОЛЖНА (SHALL) хранить внешний идентификатор документа в целевой ИБ для идемпотентного upsert и прозрачного наблюдения.

Система ДОЛЖНА (SHALL) поддерживать strategy-based resolver идентификатора:
- primary strategy: GUID документа 1С через OData (`_IDRRef` или `Ref_Key`),
- fallback strategy: детерминированный `ExternalRunKey` (`runkey-<sha256[:32]>` от `run_id + target_database_id + document_kind + period`).

#### Scenario: GUID недоступен, применяется fallback стратегия
- **GIVEN** целевая конфигурация/endpoint не возвращает стабильный GUID документа
- **WHEN** выполняется публикация
- **THEN** система использует fallback `ExternalRunKey` и записывает его в поддерживаемое поле документа
- **AND** фиксирует выбранную стратегию в audit trail run

### Requirement: OData diagnostics MUST быть прозрачными для оператора
Система ДОЛЖНА (SHALL) сохранять по каждой попытке публикации:
- целевую ИБ,
- payload summary,
- HTTP/transport ошибку,
- код доменной ошибки и сообщение,
- номер попытки и время.

#### Scenario: Оператор видит причину неудачной публикации
- **WHEN** run содержит failed-попытки публикации
- **THEN** оператор может открыть детальную диагностику по каждой ИБ
- **AND** принять решение о повторной дозаписи

