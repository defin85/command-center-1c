# organization-pool-catalog Specification

## Purpose
TBD - created by archiving change add-intercompany-pool-distribution-module. Update Purpose after archive.
## Requirements
### Requirement: Organization catalog MUST быть master-источником с внешней синхронизацией
Система ДОЛЖНА (SHALL) хранить сквозной мастер-справочник организаций на стороне orchestrator и поддерживать внешнюю синхронизацию/актуализацию.

Связь между организацией и информационной базой ДОЛЖНА (SHALL) быть `1:1`.

#### Scenario: Синхронизация обновляет существующую организацию
- **GIVEN** организация уже существует в master-справочнике
- **WHEN** внешний sync передаёт обновлённые реквизиты
- **THEN** запись обновляется без дублирования организации
- **AND** связь с ИБ остаётся единственной (`1:1`)

### Requirement: Pool topology MUST соответствовать DAG с одним root
Система ДОЛЖНА (SHALL) валидировать пул как DAG с единственным root узлом.

Multi-parent ДОЛЖЕН (SHALL) быть разрешён только для организаций верхнего уровня (прямые дети root). Для остальных уровней узел НЕ ДОЛЖЕН (SHALL NOT) иметь более одного родителя.

#### Scenario: Недопустимая связь создаёт ошибку валидации
- **GIVEN** пользователь пытается создать цикл или добавить второго родителя узлу не верхнего уровня
- **WHEN** система валидирует схему пула
- **THEN** операция отклоняется с ошибкой валидации
- **AND** структура пула не изменяется

### Requirement: Pool topology MUST поддерживать временную версионность узлов и рёбер
Система ДОЛЖНА (SHALL) хранить версии узлов и рёбер с периодами действия (`effective_from`, `effective_to`) и выбирать активную структуру по периоду расчёта.

#### Scenario: Расчёт использует актуальную версию на период
- **GIVEN** у узла и ребра есть несколько версий с разными интервалами действия
- **WHEN** запускается run за конкретный месяц или квартал
- **THEN** система использует только версии, активные в этом периоде
- **AND** неактивные версии не участвуют в расчёте

### Requirement: Import schemas MUST быть публичными переиспользуемыми шаблонами
Система ДОЛЖНА (SHALL) поддерживать публичные шаблоны схем импорта (XLSX/JSON), доступные для выбора пользователем при запуске run.

Система МОЖЕТ (MAY) хранить опциональную привязку шаблона к workflow для повторного использования проверенных схем.

#### Scenario: Пользователь выбирает шаблон при запуске импорта
- **WHEN** пользователь запускает bottom-up run
- **THEN** система предлагает список публичных шаблонов схем
- **AND** выбранный шаблон применяется для разбора входного файла/JSON

### Requirement: Organization catalog UI MUST поддерживать операторское управление организациями в tenant scope
Система ДОЛЖНА (SHALL) предоставлять на странице каталога организаций (`/pools/catalog`) операторский UI для создания и редактирования организаций без использования внешних HTTP-клиентов.

UI ДОЛЖЕН (SHALL) использовать существующий контракт upsert и сохранять доменные инварианты каталога (включая уникальность связи `organization <-> database` как `1:1`).

В рамках этого change оператор трактуется как авторизованный пользователь с доступом к `/pools/catalog` в текущей модели авторизации; change НЕ ДОЛЖЕН (SHALL NOT) вводить новую backend RBAC-модель.

#### Scenario: Оператор создаёт организацию через UI
- **GIVEN** у пользователя есть активный tenant context
- **WHEN** оператор открывает форму создания организации и заполняет обязательные поля (`inn`, `name`)
- **THEN** система отправляет upsert-запрос и создаёт запись в каталоге
- **AND** новая организация появляется в списке без ручного обновления страницы

#### Scenario: Оператор получает доменную ошибку при конфликтной привязке ИБ
- **GIVEN** выбранная ИБ уже привязана к другой организации
- **WHEN** оператор сохраняет изменения в форме организации
- **THEN** система показывает понятное сообщение о конфликте привязки
- **AND** исходные данные формы сохраняются для исправления и повторной отправки

### Requirement: Organization sync UI MUST поддерживать bulk-синхронизацию с preflight и отчётом результата
Система ДОЛЖНА (SHALL) предоставлять операторский UI для bulk-синхронизации каталога организаций через существующий sync endpoint.

В рамках MVP sync UI ДОЛЖЕН (SHALL) принимать JSON payload `rows[]`; расширенная file-ingest поддержка (CSV/XLSX parsing) НЕ ДОЛЖНА (SHALL NOT) считаться обязательной частью этого change.

Перед отправкой payload система ДОЛЖНА (SHALL) выполнять базовые preflight-проверки структуры и обязательных полей, чтобы блокировать заведомо некорректные данные до backend round-trip.

Система ДОЛЖНА (SHALL) ограничивать размер одного sync submit на уровне UI (MVP limit: не более 1000 строк).

#### Scenario: Некорректная строка блокирует запуск sync на клиенте
- **GIVEN** оператор загрузил/вставил bulk payload c пустым `inn` или `name`
- **WHEN** оператор запускает preflight/submit
- **THEN** система не отправляет запрос sync
- **AND** показывает список ошибок валидации для исправления

#### Scenario: Успешная синхронизация показывает итоговую статистику
- **GIVEN** bulk payload прошёл preflight и backend validation
- **WHEN** оператор запускает sync
- **THEN** система показывает `created`, `updated`, `skipped`, `total_rows`
- **AND** каталог организаций обновляется в текущем tenant context

#### Scenario: Payload превышает UI-лимит sync
- **GIVEN** оператор подготовил payload более 1000 строк
- **WHEN** оператор запускает preflight/submit
- **THEN** система не отправляет запрос sync
- **AND** интерфейс показывает ошибку о превышении лимита размера batch

### Requirement: Mutating actions MUST быть tenant-safe в UI каталога организаций
Система ДОЛЖНА (SHALL) блокировать mutating действия в UI каталога организаций для staff-пользователей при отсутствии явно выбранного tenant context (`active_tenant_id`) как защиту от случайных cross-tenant мутаций.

Для non-staff пользователей этот UI guard НЕ ДОЛЖЕН (SHALL NOT) добавлять дополнительную блокировку поверх server-resolved tenant context и backend authorization.

Система ДОЛЖНА (SHALL) показывать явное предупреждение о причине блокировки и о необходимости выбрать активный tenant перед mutating операциями.

#### Scenario: Staff пользователь без tenant context не может запускать мутации
- **GIVEN** пользователь является staff и не выбрал активный tenant
- **WHEN** пользователь открывает страницу `/pools/catalog`
- **THEN** кнопки `Add/Edit/Sync` недоступны
- **AND** интерфейс отображает предупреждение с объяснением ограничения

### Requirement: Organization catalog UI MUST прозрачно отображать доменные и валидационные ошибки mutating API
Система ДОЛЖНА (SHALL) отображать понятные operator-facing сообщения для backend ошибок:
`DATABASE_ALREADY_LINKED`, `DUPLICATE_ORGANIZATION_INN`, `DATABASE_NOT_FOUND`, `ORGANIZATION_NOT_FOUND`, `TENANT_NOT_FOUND`, `TENANT_CONTEXT_REQUIRED`, `VALIDATION_ERROR`.

Система ДОЛЖНА (SHALL) поддерживать отображение field-level serializer errors и fallback-обработку неизвестной ошибки без потери контекста текущей операции.

#### Scenario: Backend возвращает field-level ошибку валидации
- **GIVEN** оператор отправляет некорректные данные формы
- **WHEN** backend возвращает `success=false` и field-level `error`
- **THEN** UI показывает ошибку рядом с соответствующим полем или в явном списке полей
- **AND** оператор может исправить данные без потери введённого контента

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

Read endpoint topology snapshot ДОЛЖЕН (SHALL) возвращать актуальный `version` token, который UI использует при следующем mutating update.

#### Scenario: Второй оператор получает конфликт версии при сохранении устаревшего snapshot
- **GIVEN** два оператора редактируют один и тот же topology snapshot пула
- **AND** первый оператор уже сохранил новую версию
- **WHEN** второй оператор отправляет сохранение со старым version token
- **THEN** backend возвращает `409 Conflict` с причиной конфликта версии
- **AND** UI показывает оператору причину и не теряет введённые изменения

#### Scenario: UI получает version token из read endpoint и успешно выполняет update
- **GIVEN** оператор открыл topology snapshot в UI
- **WHEN** UI запрашивает текущую версию структуры через read endpoint
- **THEN** ответ содержит актуальный `version` token
- **AND** этот token передаётся в mutating update запрос

### Requirement: Topology mutating errors MUST использовать единый Problem Details контракт
Система ДОЛЖНА (SHALL) возвращать ошибки topology mutating endpoint'ов в формате `application/problem+json`.

Problem payload ДОЛЖЕН (SHALL) содержать поля `type`, `title`, `status`, `detail`, `code`.

#### Scenario: Конфликт версии возвращается в Problem Details формате
- **GIVEN** mutating update topology отклоняется из-за устаревшего `version` token
- **WHEN** backend формирует ответ об ошибке
- **THEN** response content-type равен `application/problem+json`
- **AND** payload содержит `status=409` и machine-readable `code`

