## ADDED Requirements
### Requirement: Pool catalog UI MUST поддерживать управление пулами без внешних HTTP-клиентов
Система ДОЛЖНА (SHALL) предоставлять на `/pools/catalog` операторский UI для создания, редактирования и деактивации пулов в текущем tenant context.

UI ДОЛЖЕН (SHALL) использовать канонический backend контракт пула и НЕ ДОЛЖЕН (SHALL NOT) требовать ручных API-вызовов для базовых mutating операций.

#### Scenario: Оператор создаёт минимальный пул для трёх организаций
- **GIVEN** в tenant каталоге есть три организации
- **WHEN** оператор создаёт пул через UI и задаёт `code` и `name`
- **THEN** пул сохраняется и появляется в списке доступных пулов на `/pools/catalog` и `/pools/runs`
- **AND** операция не требует внешнего API-клиента

### Requirement: Pool topology UI MUST поддерживать версионируемое редактирование snapshot-структуры
Система ДОЛЖНА (SHALL) предоставлять на `/pools/catalog` UI-редактор topology snapshot с указанием `effective_from`/`effective_to`, root узла и рёбер (`weight`, `min_amount`, `max_amount`).

Система ДОЛЖНА (SHALL) сохранять topology snapshot атомарно и валидировать DAG-инварианты на backend перед фиксацией изменений.

#### Scenario: Оператор формирует топологию root -> middle -> leaf
- **GIVEN** существует созданный пул и три организации
- **WHEN** оператор в topology editor сохраняет snapshot с root узлом и двумя рёбрами `root->middle`, `middle->leaf`
- **THEN** backend принимает snapshot как валидный DAG
- **AND** `/api/v2/pools/{pool_id}/graph/?date=...` возвращает сохранённую структуру для выбранной даты

#### Scenario: Оператор получает валидационную ошибку при недопустимой топологии
- **GIVEN** оператор пытается сохранить snapshot с циклом или с запрещённым вторым родителем для non-top-level узла
- **WHEN** backend валидирует topology snapshot
- **THEN** сохранение отклоняется с ошибкой валидации
- **AND** UI показывает причину ошибки без потери введённых данных

### Requirement: Pools API MUST иметь mutating операции, достаточные для full UI management
Система ДОЛЖНА (SHALL) предоставить публичный v2 API для mutating-операций пула и топологии, достаточный для работы UI без внешних клиентов.

Эти операции ДОЛЖНЫ (SHALL) быть tenant-aware и совместимыми с текущим fail-closed поведением доступа.

#### Scenario: UI выполняет полный цикл управления пулом через v2 API
- **GIVEN** оператор работает только в веб-интерфейсе
- **WHEN** он создаёт пул, сохраняет topology snapshot и открывает preview графа
- **THEN** весь цикл выполняется через документированные `/api/v2/pools/*` endpoint'ы
- **AND** ручные вызовы из Postman/curl не требуются

### Requirement: Topology snapshot mutating MUST предотвращать lost update при конкурентном редактировании
Система ДОЛЖНА (SHALL) поддерживать optimistic concurrency для mutating-операций topology snapshot через обязательный `version` token в payload.

При конфликте версий система ДОЛЖНА (SHALL) возвращать `409 Conflict` с machine-readable причиной, а UI ДОЛЖЕН (SHALL) сохранять введённые данные до повторной попытки.

#### Scenario: Второй оператор получает конфликт версии при сохранении устаревшего snapshot
- **GIVEN** два оператора редактируют один и тот же topology snapshot пула
- **AND** первый оператор уже сохранил новую версию
- **WHEN** второй оператор отправляет сохранение со старым version token
- **THEN** backend возвращает `409 Conflict` с причиной конфликта версии
- **AND** UI показывает оператору причину и не теряет введённые изменения
