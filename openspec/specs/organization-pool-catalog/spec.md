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

Система ДОЛЖНА (SHALL) предоставлять на странице `/pools/templates` operator-facing UI для создания и редактирования шаблонов импорта (`code`, `name`, `format`, `is_public`, `is_active`, `workflow_template_id`, `schema`, `metadata`) без использования внешних HTTP-клиентов.

Система МОЖЕТ (MAY) хранить опциональную привязку шаблона к workflow для повторного использования проверенных схем.

#### Scenario: Пользователь выбирает шаблон при запуске импорта
- **WHEN** пользователь запускает bottom-up run
- **THEN** система предлагает список публичных шаблонов схем
- **AND** выбранный шаблон применяется для разбора входного файла/JSON

#### Scenario: Оператор редактирует существующий шаблон через UI
- **GIVEN** в каталоге шаблонов есть существующий template
- **WHEN** оператор открывает edit-flow на `/pools/templates`, меняет `name`/`schema`/`metadata` и сохраняет
- **THEN** изменения persist'ятся через канонический API update endpoint
- **AND** обновлённые данные отображаются в таблице шаблонов без ручного API-вызова

#### Scenario: Невалидный JSON блокирует сохранение шаблона
- **GIVEN** оператор ввёл невалидный JSON в `schema` или `metadata`
- **WHEN** оператор пытается сохранить шаблон
- **THEN** UI блокирует submit
- **AND** показывает понятную ошибку валидации без потери введённого содержимого

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

### Requirement: Topology API MUST сохранять и возвращать metadata, достаточную для document-policy slot управления
Система ДОЛЖНА (SHALL) в mutating topology snapshot API сохранять `node.metadata` и `edge.metadata` без потери данных, достаточных для structural topology authoring и выбора publication slot, включая `edge.metadata.document_policy_key`.

Система ДОЛЖНА (SHALL) в read-path topology/graph API возвращать metadata узлов и рёбер, чтобы оператор мог безопасно редактировать structural topology и slot selectors без внешних инструментов.

Система НЕ ДОЛЖНА (SHALL NOT) принимать в штатном mutating authoring path legacy payload `edge.metadata.document_policy` или `pool.metadata.document_policy` после cutover.

#### Scenario: Оператор сохраняет `document_policy_key` в edge metadata и видит его в read-path
- **GIVEN** оператор отправляет topology snapshot с `edge.metadata.document_policy_key`
- **WHEN** snapshot сохраняется и затем читается через graph/topology endpoint
- **THEN** response содержит сохранённое `edge.metadata.document_policy_key`
- **AND** оператор может выполнить повторное редактирование без потери metadata

#### Scenario: Legacy document policy payload отклоняется на этапе topology save
- **GIVEN** оператор отправляет topology snapshot с `edge.metadata.document_policy` или `pool.metadata.document_policy`
- **WHEN** backend выполняет pre-persist validation
- **THEN** запрос отклоняется fail-closed валидационной ошибкой
- **AND** topology snapshot в БД не изменяется

### Requirement: Topology metadata contract MUST быть schema-stable для API и клиента
Система ДОЛЖНА (SHALL) публиковать в topology/graph API явные поля `node.metadata` и `edge.metadata` как часть стабильного read-model контракта, включая `edge.metadata.document_policy_key`.

Система ДОЛЖНА (SHALL) сохранять round-trip совместимость structural metadata: пользовательские поля metadata не теряются между mutating и последующим read-path вызовом.

#### Scenario: Round-trip topology metadata не теряет structural поля и slot selector
- **GIVEN** snapshot содержит `node.metadata`, `edge.metadata` и валидный `edge.metadata.document_policy_key`
- **WHEN** snapshot сохраняется и затем читается через graph/topology API
- **THEN** response содержит те же metadata структуры без потери пользовательских полей
- **AND** frontend может безопасно повторно отправить snapshot без реконструкции metadata вне API

### Requirement: Pool catalog UI MUST быть организован как task-oriented workspace
Система ДОЛЖНА (SHALL) организовать `/pools/catalog` как набор логических рабочих зон (организации, пулы, topology editing, graph preview), чтобы оператор видел только релевантные controls и данные текущего шага.

Система ДОЛЖНА (SHALL) уменьшить количество одновременно видимых mutating controls и не смешивать независимые сценарии в одном визуальном блоке.

#### Scenario: Оператор управляет организациями без шума topology editor
- **GIVEN** оператор работает в зоне управления организациями на `/pools/catalog`
- **WHEN** оператор выполняет create/edit/sync организаций
- **THEN** интерфейс не требует взаимодействия с controls topology editor
- **AND** контент topology не доминирует в текущем контексте задачи

#### Scenario: Topology editing выполняется в отдельном фокусном контексте
- **GIVEN** оператор переключился к редактированию topology snapshot
- **WHEN** оператор добавляет node/edge и сохраняет snapshot
- **THEN** интерфейс показывает только релевантные topology controls и validation feedback
- **AND** выбранный pool context сохраняется между рабочими зонами

#### Scenario: Advanced metadata поля скрыты по умолчанию
- **GIVEN** оператор открывает topology editor
- **WHEN** он выполняет базовое редактирование структуры
- **THEN** advanced metadata/JSON controls скрыты по умолчанию
- **AND** доступны по явному действию (progressive disclosure)

### Requirement: Pool catalog API MUST предоставлять полный каталог OData-метаданных для выбранной ИБ
Система ДОЛЖНА (SHALL) предоставлять read endpoint каталога метаданных для выбранной информационной базы, достаточный для интерактивной сборки `Document policy` и `Edge metadata`.

Каталог ДОЛЖЕН (SHALL) включать минимум:
- список документов (`entity_name`, `display_name`);
- список реквизитов документа (`fields[]`);
- список табличных частей (`table_parts[]`);
- список реквизитов строки табличной части (`row_fields[]`).

Каталог ДОЛЖЕН (SHALL) возвращаться в нормализованном machine-readable формате, пригодном для UI form-builder без дополнительного парсинга CSDL на клиенте.

#### Scenario: UI получает каталог документов и реквизитов для builder-режима
- **GIVEN** оператор выбрал ИБ в topology editor
- **WHEN** UI запрашивает metadata catalog через публичный endpoint
- **THEN** backend возвращает документы, реквизиты и табличные части в нормализованной структуре
- **AND** UI может построить интерактивные селекторы без ручного ввода имён полей

### Requirement: Metadata catalog retrieval MUST использовать persisted snapshot в БД и Redis только как ускоритель
Система ДОЛЖНА (SHALL) хранить нормализованный metadata catalog как canonical persisted snapshot, пригодный для reuse между несколькими ИБ в рамках одной tenant-scoped business configuration identity, а не как database-local current snapshot по `database_id` alone.

Canonical metadata snapshot identity ДОЛЖНА (SHALL) включать только:
- `config_name`;
- `config_version`.

`config_name` и `config_version` в рамках этого requirement:
- ДОЛЖНЫ (SHALL) описывать business-level identity конфигурации;
- НЕ ДОЛЖНЫ (SHALL NOT) вычисляться из `Database.base_name`, `Database.infobase_name`, `Database.name` или `Database.version`;
- ДОЛЖНЫ (SHALL) по смыслу резолвиться из root configuration properties, а runtime'ом по умолчанию читаться из persisted business profile, верифицированного root configuration export path.

`config_name` ДОЛЖЕН (SHALL) резолвиться в порядке:
- root configuration `Synonym` для локали `ru`;
- первый доступный synonym entry;
- root configuration `Name`.

`config_version` ДОЛЖЕН (SHALL) резолвиться из root configuration `Version`.

Runtime acquisition contract ДОЛЖЕН (SHALL) быть profile-driven:
- metadata refresh/read path ДОЛЖЕН (SHALL) использовать persisted business profile, если он уже известен и не требует re-verify;
- система ДОЛЖНА (SHALL) использовать `config_generation_id` только как cheap equal/not-equal marker, определяющий необходимость re-verify;
- если profile отсутствует или generation marker указывает на изменение конфигурации, система ДОЛЖНА (SHALL) запускать async verification/bootstrap job;
- verification/bootstrap job ДОЛЖЕН (SHALL) переиспользовать существующую execution chain `workflow/operations -> worker -> driver`;
- standalone verification/bootstrap execution ДОЛЖЕН (SHALL) использовать executor `ibcmd_cli`, а не direct shell/probe path в orchestrator;
- standalone verification/bootstrap execution ДОЛЖЕН (SHALL) использовать existing public `execute-ibcmd-cli` contract или эквивалентный operation template / workflow step, который в итоге вызывает тот же `ibcmd_cli` executor;
- если verification является частью большего maintenance flow, она ДОЛЖНА (SHALL) встраиваться как workflow step, который в итоге использует тот же `ibcmd_cli` execution path;
- default verification/bootstrap command ДОЛЖЕН (SHALL) использовать existing schema-driven `command_id = infobase.config.export.objects` с root object selector `Configuration`;
- verification job ДОЛЖЕН (SHALL) парсить `Configuration.xml` и сохранять как минимум `Name`, `Synonym`, `Vendor`, `Version`;
- worker result/artifact contract ДОЛЖЕН (SHALL) позволять orchestrator получить `Configuration.xml` или его нормализованное содержимое для обновления persisted business profile;
- hot path metadata refresh НЕ ДОЛЖЕН (SHALL NOT) требовать full configuration export, Designer/X11 invocation или обхода worker/driver chain для каждой ИБ.

Canonical snapshot identity НЕ ДОЛЖНА (SHALL NOT) включать:
- `database_id`;
- имя ИБ;
- `metadata_hash`;
- `extensions_fingerprint`;
- `config_generation_id`.

Read/refresh path МОЖЕТ (MAY) стартовать от выбранной ИБ, но:
- конкретная ИБ ДОЛЖНА (SHALL) использоваться только как auth/probe source и provenance anchor;
- ИБ с одинаковыми `config_name + config_version` ДОЛЖНЫ (SHALL) переиспользовать один canonical business-scoped snapshot;
- различие published OData metadata surface НЕ ДОЛЖНО (SHALL NOT) создавать отдельную compatibility identity.

`metadata_hash`, `extensions_fingerprint` и `config_generation_id` ДОЛЖНЫ (SHALL) сохраняться и возвращаться как provenance/diagnostics markers publication state.

Если выбранная ИБ отличается по published metadata surface от canonical business-scoped snapshot, API ДОЛЖЕН (SHALL):
- возвращать canonical business-scoped snapshot;
- сохранять provenance последней ИБ, подтвердившей этот snapshot;
- возвращать явную diagnostics indication publication drift для выбранной ИБ.

#### Scenario: Две ИБ с одинаковой конфигурацией и релизом переиспользуют один snapshot независимо от имени ИБ
- **GIVEN** в tenant есть две ИБ с разными именами
- **AND** root configuration properties у них дают одинаковые `config_name` и `config_version`
- **WHEN** оператор запрашивает metadata catalog для второй ИБ после refresh первой
- **THEN** backend возвращает тот же canonical business-scoped snapshot
- **AND** имя ИБ не участвует в compatibility identity

#### Scenario: Одинаковая business identity переиспользует snapshot при publication drift
- **GIVEN** две ИБ имеют одинаковые `config_name` и `config_version`
- **AND** состав опубликованных через OData metadata objects у них различается
- **WHEN** backend refresh'ит metadata catalog для второй ИБ
- **THEN** система не создаёт новую compatibility identity только из-за отличия `metadata_hash`
- **AND** response содержит diagnostics indication publication drift
- **AND** provenance указывает, какая ИБ подтвердила canonical business-scoped snapshot

#### Scenario: Persisted business profile используется как default runtime source
- **GIVEN** для выбранной ИБ уже сохранён persisted business profile
- **AND** `config_generation_id` не указывает на изменение конфигурации с момента последней верификации
- **WHEN** backend выполняет metadata read или refresh
- **THEN** runtime использует persisted `config_name` и `config_version`
- **AND** не требует full export, Designer invocation или direct shell execution в hot path

#### Scenario: Business identity конфигурации верифицируется selective export root object
- **GIVEN** persisted business profile отсутствует или требует re-verify после изменения generation marker
- **WHEN** backend запускает verification/bootstrap job для выбранной ИБ
- **THEN** job проходит через существующую execution chain `workflow/operations -> worker -> driver`
- **AND** использует executor `ibcmd_cli`
- **AND** использует existing `command_id = infobase.config.export.objects` с root object selector `Configuration`
- **AND** парсит `Configuration.xml`
- **AND** `config_name` берётся из root configuration `Synonym` или fallback `Name`
- **AND** `config_version` берётся из root configuration `Version`
- **AND** identity не зависит от имени ИБ

#### Scenario: Generation marker триггерит re-verify, но не становится business identity
- **GIVEN** система хранит `config_generation_id` для ранее верифицированного business profile
- **WHEN** очередной cheap probe возвращает другой `config_generation_id`
- **THEN** система помечает business profile как требующий re-verify
- **AND** запускает async verification job
- **AND** выполняет probe через existing `command_id = infobase.config.generation-id` по тому же `ibcmd_cli`/worker path
- **AND** не использует `config_generation_id` как reuse key между ИБ

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

### Requirement: Topology editor UI MUST поддерживать structural metadata и edge policy slots
Система ДОЛЖНА (SHALL) предоставлять в `/pools/catalog` topology editor для structural `node.metadata` / `edge.metadata` и явного выбора `edge.metadata.document_policy_key`.

Topology editor ДОЛЖЕН (SHALL) быть slot-oriented workspace, а не legacy document-policy editor.

Topology editor НЕ ДОЛЖЕН (SHALL NOT) оставаться shipped surface для inline `document_policy` authoring или import.

Для pool, зависящих от legacy topology policy, UI ДОЛЖЕН (SHALL) входить в blocking remediation state и направлять оператора в canonical decision/binding remediation flow.

Topology editor ДОЛЖЕН (SHALL) показывать status coverage для `document_policy_key` относительно выбранного canonical binding context, когда такой context доступен.

Coverage НЕ ДОЛЖЕН (SHALL NOT) отображаться как resolved, если canonical binding context не выбран и не может быть auto-resolved детерминированно.

#### Scenario: Новый edge получает slot selector без inline policy builder
- **GIVEN** оператор добавляет новый edge в topology editor
- **WHEN** UI рендерит controls для edge metadata
- **THEN** structural metadata и `document_policy_key` остаются доступны
- **AND** inline `document_policy` editor/import не предлагается как shipped action

#### Scenario: Editor показывает coverage selected slot относительно binding
- **GIVEN** оператор редактирует edge с `document_policy_key=sale`
- **AND** для выбранного pool доступен canonical binding с pinned slot `sale`
- **WHEN** UI рендерит edge editor
- **THEN** editor показывает, что slot coverage резолвится успешно
- **AND** оператор видит связь между topology edge и binding slot без перехода в raw JSON

#### Scenario: Coverage context ambiguous не маскируется как valid slot coverage
- **GIVEN** для одного `pool` существует несколько active bindings
- **AND** оператор не выбрал явный binding context для topology coverage
- **WHEN** UI рендерит edge editor
- **THEN** editor показывает, что coverage context ambiguous или unavailable
- **AND** не маркирует `document_policy_key` как resolved без детерминированного binding context

#### Scenario: Legacy topology переводит UI в remediation state
- **GIVEN** выбранный pool или topology snapshot содержит legacy `edge.metadata.document_policy` или `pool.metadata.document_policy`
- **WHEN** оператор открывает topology editor
- **THEN** UI показывает blocking remediation state
- **AND** normal topology save для legacy policy authoring недоступен
- **AND** оператор получает handoff к `/decisions` и binding remediation flow

### Requirement: UI MUST сохранять raw JSON fallback и round-trip совместимость metadata
Система ДОЛЖНА (SHALL) сохранять round-trip совместимость legacy `edge.metadata` и migration payload при explicit compatibility/migration path.

Система НЕ ДОЛЖНА (SHALL NOT) терять:
- пользовательские/неизвестные keys `edge.metadata`;
- legacy `document_policy`, пока migration не подтверждена;
- provenance связи между legacy edge и resulting decision resource revision.

Raw JSON fallback МОЖЕТ (MAY) использоваться в explicit compatibility или decision-resource editor, но НЕ ДОЛЖЕН (SHALL NOT) оставаться default topology authoring mode для новых workflow-centric схем.

#### Scenario: Migration path сохраняет unknown metadata keys и provenance
- **GIVEN** legacy edge содержит `document_policy` и дополнительные unknown metadata keys
- **WHEN** оператор выполняет migration/import
- **THEN** unknown keys `edge.metadata` сохраняются без потери
- **AND** UI/backend фиксируют provenance `edge -> decision revision -> binding ref`

### Requirement: Organization catalog MUST иметь явный binding к canonical Party
Система ДОЛЖНА (SHALL) поддерживать явный binding между `Organization` и `Party` (MVP `1:1`) для устранения дублирования источников истины.

Система ДОЛЖНА (SHALL) применять ownership policy:
- `Organization` владеет topology/pool-catalog полями;
- `Party` владеет каноническими master-data реквизитами, используемыми publication runtime.

Система ДОЛЖНА (SHALL) выполнять backfill `Organization -> Party` детерминированно:
- match-кандидаты определяются по `(tenant_id, inn, is_our_organization=true)` и дополнительно по `kpp`, если `Organization.kpp` непустой;
- при ровно одном кандидате binding создаётся автоматически;
- при `0` или `>1` кандидате binding не создаётся, запись попадает в remediation-list.

Система НЕ ДОЛЖНА (SHALL NOT) допускать публикационные сценарии, требующие `our_organization` role, без валидного `Organization -> Party` binding.

#### Scenario: Existing organization получает canonical Party binding в миграции
- **GIVEN** в tenant уже есть записи `Organization` до включения master-data workspace
- **WHEN** выполняется rollout с backfill `Organization -> Party`
- **THEN** каждая организация получает валидный binding или попадает в явный remediation-list
- **AND** система не создаёт silent fallback соответствия

#### Scenario: Публикационный preflight блокируется при отсутствии binding
- **GIVEN** организация участвует в topology/pool run
- **AND** для неё отсутствует валидный `Organization -> Party` binding
- **WHEN** система выполняет pre-publication checks для run
- **THEN** run блокируется fail-closed до OData side effects
- **AND** оператор получает machine-readable диагностику с контекстом организации

#### Scenario: Неоднозначный backfill не создаёт автоматический binding
- **GIVEN** для одной `Organization` найдено несколько `Party`-кандидатов по tenant/INN
- **WHEN** выполняется backfill `Organization -> Party`
- **THEN** binding не создаётся автоматически
- **AND** организация добавляется в remediation-list для ручного исправления

### Requirement: Pool catalog workflow bindings MUST использовать isolated binding workspace и canonical CRUD
Система ДОЛЖНА (SHALL) управлять workflow bindings на `/pools/catalog` через dedicated attachment workspace и dedicated attachment endpoints, backed by the same canonical store, который использует runtime resolution.

`/pools/catalog` ДОЛЖЕН (SHALL) трактовать `pool_workflow_binding` как pool-scoped attachment к pinned `binding_profile_revision_id`, а не как primary inline authoring surface для reusable workflow/slot logic.

Pool upsert contract НЕ ДОЛЖЕН (SHALL NOT) нести canonical attachment payload и НЕ ДОЛЖЕН (SHALL NOT) переписывать attachment state как side effect редактирования базовых полей пула.

Attachment read path ДОЛЖЕН (SHALL) возвращать server-managed `revision`, pinned `binding_profile_revision_id`, optional display `binding_profile_revision_number` и достаточный read-only summary resolved profile для lineage visibility и topology slot coverage diagnostics.

Attachment workspace ДОЛЖЕН (SHALL) показывать read-only resolved profile summary с pinned workflow lineage и topology slot coverage diagnostics, не разрешая inline mutation reusable workflow/slot/parameter/role-mapping payload.

UI ДОЛЖЕН (SHALL) разделять:
- mutating операции над базовыми полями `pool`;
- mutating операции над `pool_workflow_binding` как attachment;
- authoring reusable binding profile revisions в dedicated profile catalog.

Для default multi-attachment save UI ДОЛЖЕН (SHALL) использовать публичный collection-level atomic save contract `PUT /api/v2/pools/workflow-bindings/` поверх canonical attachment store и НЕ ДОЛЖЕН (SHALL NOT) полагаться на последовательность client-side `upsert/delete`, которая допускает partial apply.

Default collection-save UI ДОЛЖЕН (SHALL) использовать `collection_etag` / `expected_collection_etag` как единственный workspace concurrency contract. Per-attachment `revision` НЕ ДОЛЖЕН (SHALL NOT) использоваться как primary conflict token для default multi-binding save.

При collection conflict UI ДОЛЖЕН (SHALL) сохранять введённые данные формы, показывать причину конфликта и предлагать reload canonical collection без потери локального edit state.

Если оператору требуется изменить reusable workflow/slot logic pinned profile revision, `/pools/catalog` НЕ ДОЛЖЕН (SHALL NOT) quietly редактировать эту логику inline внутри attachment workspace и ДОЛЖЕН (SHALL) направлять на отдельный route `/pools/binding-profiles`.

Если currently pinned reusable profile revision больше не присутствует в latest profile catalog (например, profile deactivated или catalog уже указывает на более новую revision), attachment workspace ДОЛЖЕН (SHALL) сохранять видимость этого pinned revision как `current` context и НЕ ДОЛЖЕН (SHALL NOT) silently re-pin attachment на latest revision.

Если canonical attachment collection пуста, но backend сообщает blocking remediation из-за legacy metadata/document_policy residue, attachment workspace ДОЛЖЕН (SHALL) показывать blocking remediation и отключать default collection save до устранения legacy state.

#### Scenario: Сохранение базовых полей пула не переписывает workflow attachments
- **GIVEN** оператор редактирует `code` или `name` пула в `/pools/catalog`
- **AND** у пула уже есть active workflow attachments
- **WHEN** оператор сохраняет только базовые поля пула
- **THEN** UI использует pool upsert path без canonical attachment payload
- **AND** существующие workflow attachments не теряются и не переписываются

#### Scenario: Attachment editor использует тот же canonical CRUD, что и runtime
- **GIVEN** оператор добавляет attachment или меняет pinned profile revision в `/pools/catalog`
- **WHEN** изменение сохраняется
- **THEN** UI читает и сохраняет canonical collection через `GET/PUT /api/v2/pools/workflow-bindings/`
- **AND** следующий create-run/read-model видит это же изменение без дополнительного metadata sync шага

#### Scenario: Workspace направляет в profile catalog для правки reusable логики
- **GIVEN** оператор открыл attachment в `/pools/catalog`
- **AND** attachment pinned на existing `binding_profile_revision`
- **WHEN** оператору нужно изменить workflow/slot mapping этой схемы
- **THEN** UI направляет его на `/pools/binding-profiles`
- **AND** attachment workspace сохраняет только pool-local scope и profile reference

#### Scenario: Attachment workspace показывает resolved profile lineage и slot coverage diagnostics
- **GIVEN** у выбранного пула есть topology edges с publication slot selectors
- **AND** attachment pinned на reusable profile revision с resolved decision refs
- **WHEN** оператор открывает binding workspace на `/pools/catalog`
- **THEN** UI показывает read-only resolved profile summary, pinned workflow lineage и slot coverage diagnostics для topology edges
- **AND** unresolved slot coverage блокирует default attachment save до исправления pinned profile reference или topology slot selectors

#### Scenario: Pinned revision остаётся видимой вне latest profile catalog
- **GIVEN** pool attachment pinned на reusable profile revision, которая уже не является latest revision в profile catalog
- **WHEN** оператор открывает attachment editor в `/pools/catalog`
- **THEN** UI продолжает показывать эту pinned revision как current lineage context
- **AND** attachment не перепривязывается автоматически на latest revision без явного выбора оператора

#### Scenario: Legacy metadata residue переводит workspace в blocking remediation state
- **GIVEN** backend вернул canonical attachment collection для пула
- **AND** collection пуста
- **AND** backend указал blocking remediation из-за legacy metadata/document_policy residue
- **WHEN** оператор открывает binding workspace в `/pools/catalog`
- **THEN** UI показывает blocking remediation
- **AND** default collection save disabled до устранения legacy state

#### Scenario: Stale collection etag в catalog editor возвращает conflict без потери формы
- **GIVEN** оператор редактирует workflow attachments в `/pools/catalog`
- **AND** другой оператор уже сохранил новую canonical collection
- **WHEN** первый оператор пытается отправить состояние со старым `expected_collection_etag`
- **THEN** backend возвращает machine-readable conflict по `expected_collection_etag`
- **AND** UI сохраняет введённые данные для повторной попытки

### Requirement: Pool catalog metadata client MUST использовать generated OpenAPI contract как единственный typed source-of-truth
Система ДОЛЖНА (SHALL) использовать generated OpenAPI client/models как единственный typed source-of-truth для shipped frontend path, который читает `/api/v2/pools/odata-metadata/catalog/` и `/api/v2/pools/odata-metadata/catalog/refresh/`.

Hand-written DTO или mirror-типы для этого surface НЕ ДОЛЖНЫ (SHALL NOT) оставаться runtime-контрактом default `/pools/catalog` metadata workspace.

Drift между runtime serializer, OpenAPI source, generated client и shipped frontend consumer ДОЛЖЕН (SHALL) блокировать релиз как quality gate.

Hand-written types для этого surface НЕ ДОЛЖНЫ (SHALL NOT) существовать в exported runtime modules. Они допустимы только в test fixtures и one-off migration helpers вне shipped runtime import graph.

#### Scenario: Новые shared snapshot markers проходят через один source-of-truth
- **GIVEN** metadata catalog contract расширен новыми полями shared snapshot provenance
- **WHEN** обновляется OpenAPI source и выполняется codegen
- **THEN** shipped frontend consumer читает эти поля через generated model
- **AND** отдельный hand-written DTO не требуется для корректной типизации default path

#### Scenario: Drift между generated client и shipped consumer блокирует release
- **GIVEN** runtime/OpenAPI metadata catalog contract изменён
- **WHEN** generated client или frontend consumer не синхронизирован с новым контрактом
- **THEN** parity gate завершается ошибкой
- **AND** stale hand-written DTO не может silently оставаться источником истины для shipped path

### Requirement: Topology editor MUST hand off metadata maintenance to `/databases`
Система ДОЛЖНА (SHALL) трактовать `/pools/catalog` topology editor как consumer surface для metadata-aware authoring, а не как primary mutate surface для configuration profile или metadata snapshot maintenance.

UI МОЖЕТ (MAY) показывать в builder-контексте readonly indicators текущего metadata state, но НЕ ДОЛЖЕН (SHALL NOT) прятать primary controls `Load metadata`, `Refresh metadata` или эквивалентные metadata maintenance actions внутри edge-policy authoring path как единственный canonical UX.

Если authoring path блокируется из-за отсутствующего/устаревшего metadata context, `/pools/catalog` ДОЛЖЕН (SHALL) направлять оператора в `/databases` для управления configuration profile / metadata snapshot.

#### Scenario: Builder показывает handoff вместо hidden maintenance controls
- **GIVEN** оператор редактирует edge metadata в `/pools/catalog`
- **WHEN** ему нужен metadata maintenance action для выбранной ИБ
- **THEN** UI показывает status и явный handoff в `/databases`
- **AND** primary metadata maintenance control не спрятан внутри topology builder как единственный discoverable path

#### Scenario: Сохранение topology блокируется и направляет в canonical surface
- **GIVEN** topology save отклонён из-за отсутствующего или неактуального metadata context
- **WHEN** UI показывает fail-closed ошибку
- **THEN** сообщение объясняет, что исправление выполняется через `/databases`
- **AND** topology editor не притворяется canonical местом управления snapshot/profile

### Requirement: `/pools/catalog` MUST использовать task-first platform workspace composition
Система ДОЛЖНА (SHALL) реализовать `/pools/catalog` как platform workspace, где:
- catalog pools является primary context;
- pool basics, topology authoring, workflow attachment workspace и remediation guidance разделены по задаче;
- оператор может работать с attachment/edit/remediation без конкурирующего monolithic page canvas, в котором одновременно открыты все режимы.

Route ДОЛЖЕН (SHALL) сохранять selected pool, active task context и relevant secondary state в URL-addressable форме, чтобы deep-link, reload и browser back/forward сохраняли операторский контекст.

Primary mutate flows для attachment workspace НЕ ДОЛЖНЫ (SHALL NOT) оставаться raw inline mega-editor path. Они ДОЛЖНЫ (SHALL) использовать canonical form shells, platform-owned secondary surfaces или явный handoff в dedicated canonical route.

#### Scenario: Deep-link возвращает оператора в тот же pool workspace context
- **GIVEN** оператор открыл `/pools/catalog` для конкретного pool и attachment/remediation context
- **WHEN** страница перезагружается или ссылка открывается повторно
- **THEN** UI восстанавливает selected pool и task context
- **AND** оператор продолжает работу без повторного ручного выбора нужного пула и вкладки

#### Scenario: Attachment workflow не конкурирует с topology и pool basics в одном default canvas
- **GIVEN** оператору нужно изменить attachment state или пройти remediation в `/pools/catalog`
- **WHEN** он открывает соответствующий flow
- **THEN** UI переводит его в dedicated secondary surface или canonical task section
- **AND** topology, pool basics и attachment authoring не остаются одновременно primary competing flows на одном default экране

#### Scenario: Handoff в attachment workspace сохраняет shell и pool task context
- **GIVEN** оператор приходит в `/pools/catalog` из другого frontend route через attachment/remediation handoff
- **WHEN** handoff передаёт `pool_id`, `tab` или другой relevant task context
- **THEN** UI открывает нужный pool workspace и attachment task без повторного ручного выбора
- **AND** переход не требует full-document reload и не пересоздаёт shared shell только ради этого handoff

### Requirement: `/pools/catalog` MUST поддерживать template-based topology instantiation для типовых pool схем
Система ДОЛЖНА (SHALL) предоставлять на `/pools/catalog` operator-facing path создания и обновления topology через выбор `topology_template_revision` и назначение concrete организаций в template slot-ы.

Этот path ДОЛЖЕН (SHALL) быть preferred reuse path для типовых новых pool схем, где shape graph повторяется между несколькими `pool`.

Этот change НЕ ДОЛЖЕН (SHALL NOT) требовать automatic in-place conversion already existing pools; template-based path применяется к новым или явно пересозданным после hard reset `pool`.

#### Scenario: Оператор создаёт новый pool из reusable topology template
- **GIVEN** в tenant catalog опубликована активная `topology_template_revision`
- **WHEN** оператор создаёт новый `pool` через `/pools/catalog` и выбирает template-based path
- **THEN** интерфейс предлагает выбрать revision и назначить организации в required slot-ы
- **AND** оператору не нужно вручную собирать все узлы и рёбра заново edge-by-edge

#### Scenario: Existing pool не переводится в template mode как побочный эффект rollout
- **GIVEN** в tenant уже существует `pool`, собранный вручную до появления topology templates
- **WHEN** оператор открывает `/pools/catalog` после rollout
- **THEN** existing `pool` не получает template revision и slot assignments автоматически
- **AND** переход на template-based path требует явного пересоздания или отдельного операторского действия вне этого change

### Requirement: Manual topology authoring MUST оставаться fallback path для нестандартных схем
Система ДОЛЖНА (SHALL) сохранять manual topology editor как fallback/remediation path для нестандартных или разовых схем, которые не укладываются в reusable template.

Manual topology authoring НЕ ДОЛЖЕН (SHALL NOT) оставаться единственным штатным способом тиражирования типовых схем между pool.

#### Scenario: Нестандартная схема всё ещё может быть собрана вручную
- **GIVEN** оператору нужна разовая topology, для которой нет подходящего template
- **WHEN** оператор выбирает manual topology authoring
- **THEN** current snapshot editor остаётся доступным
- **AND** отсутствие подходящего template не блокирует создание или изменение `pool`

### Requirement: Template-based instantiation MUST сохранять concrete graph compatibility с existing read APIs
Система ДОЛЖНА (SHALL) после template-based instantiation возвращать concrete materialized topology через existing `/api/v2/pools/{pool_id}/graph/` и snapshots read endpoints.

Operator-facing graph preview, topology diagnostics и runtime consumers НЕ ДОЛЖНЫ (SHALL NOT) требовать отдельный template-specific read path как единственный источник active pool graph в MVP.

#### Scenario: Graph preview читает concrete topology после template instantiation
- **GIVEN** `pool` был создан или обновлён через template-based instantiation
- **WHEN** оператор открывает graph preview или topology read path
- **THEN** existing graph API возвращает concrete active nodes и edges этого `pool`
- **AND** UI/runtime продолжают работать через current graph contract без дополнительной ручной реконструкции template shape

### Requirement: `/pools/catalog` MUST hand off reusable topology template authoring to dedicated workspace
Система ДОЛЖНА (SHALL) рассматривать `/pools/catalog` как consumer path для topology template instantiation, а reusable topology template authoring ДОЛЖНА (SHALL) выполнять через dedicated route `/pools/topology-templates`.

Если оператору в `/pools/catalog` не хватает подходящего topology template или нужно изменить reusable shape graph, интерфейс НЕ ДОЛЖЕН (SHALL NOT) оставлять его в dead-end состоянии с требованием вручную заполнять catalog вне UI.

#### Scenario: В topology editor отсутствует подходящий reusable template
- **GIVEN** оператор открыл `/pools/catalog` и находится в template-based topology path
- **AND** topology template catalog пуст или в нём нет подходящей reusable схемы
- **WHEN** оператору нужно создать новый reusable template
- **THEN** UI показывает явный handoff в `/pools/topology-templates`
- **AND** оператору не нужно покидать product surface ради прямого API-вызова

### Requirement: Handoff между `/pools/catalog` и `/pools/topology-templates` MUST сохранять pool topology context
Система ДОЛЖНА (SHALL) сохранять selected `pool`, topology task context и relevant return state при переходе из `/pools/catalog` в `/pools/topology-templates` и обратно.

Возврат из reusable template workspace НЕ ДОЛЖЕН (SHALL NOT) требовать повторного ручного выбора `pool` и topology task, если оператор пришёл из конкретного pool context.

#### Scenario: Оператор возвращается из reusable template workspace в тот же pool topology task
- **GIVEN** оператор открыл `/pools/catalog` для конкретного `pool` и перешёл в `/pools/topology-templates` через topology handoff
- **WHEN** он завершает create или revise flow reusable template и возвращается назад
- **THEN** `/pools/catalog` восстанавливает тот же `pool` и topology task context
- **AND** оператор может продолжить instantiation без повторного ручного выбора нужного pool

### Requirement: Template-based pool assembly MUST require topology-aware reusable execution packs
Система ДОЛЖНА (SHALL) использовать в template-based pool authoring path на `/pools/catalog` следующую ownership модель:
- `topology_template_revision` задаёт reusable structural graph и `document_policy_key`;
- `pool` задаёт concrete `slot_key -> organization_id`;
- attached `execution-pack revision` задаёт reusable executable implementations через topology-aware participant aliases;
- concrete participant refs НЕ ДОЛЖНЫ (SHALL NOT) быть обязательной частью reusable execution-pack contract для новых/revised template-oriented pools.

При attach, preview или save template-based path система ДОЛЖНА (SHALL) валидировать выбранный execution pack одновременно по:
- structural slot coverage;
- topology-aware master-data readiness для topology-derived `party` / `contract` fields.

Если execution pack structurally совпадает по `slot_key`, но использует hardcoded concrete participant refs для topology-derived reusable slots, `/pools/catalog` ДОЛЖЕН (SHALL):
- fail-close'ить normal attach/preview/create-run path для такого template-oriented flow;
- показывать blocking diagnostic;
- направлять оператора в `/pools/execution-packs` и `/decisions` как canonical remediation surfaces.

Diagnostic contract ДОЛЖЕН (SHALL) использовать stable machine-readable code, чтобы `/pools/catalog` и `/pools/execution-packs` объясняли одну и ту же incompatibility одинаково.

Historical pools и historical execution packs НЕ ДОЛЖНЫ (SHALL NOT) автоматически repair'иться этим change.

#### Scenario: Оператор собирает новый pool из template без hardcoded counterparties
- **GIVEN** оператор создаёт или revises pool через template-based path
- **AND** выбирает `topology_template_revision`
- **AND** назначает concrete `slot_key -> organization_id`
- **AND** выбранная `execution-pack revision` проходит topology-aware compatibility
- **WHEN** оператор сохраняет binding/topology и запускает preview
- **THEN** shipped path не требует отдельного ввода hardcoded `organization`, `counterparty` или `contract owner` refs в reusable execution pack
- **AND** concrete participants выводятся из slot assignments и topology-aware aliases

#### Scenario: Incompatible execution pack блокирует template-based attach path
- **GIVEN** оператор выбрал `topology_template_revision` и execution pack с matched `slot_key`
- **AND** один из reusable slots использует concrete participant refs вместо topology-aware aliases
- **WHEN** оператор пытается сохранить binding, выполнить preview или стартовать run на template-based path
- **THEN** `/pools/catalog` возвращает blocking compatibility diagnostic
- **AND** normal path не продолжает attach или runtime start
- **AND** оператор получает явный handoff в `/pools/execution-packs` и `/decisions`

#### Scenario: Catalog использует stable code для reusable master-data incompatibility
- **GIVEN** template-based path заблокирован из-за execution pack с concrete participant refs
- **WHEN** `/pools/catalog` показывает blocking remediation
- **THEN** remediation использует machine-readable code `EXECUTION_PACK_TEMPLATE_INCOMPATIBLE`
- **AND** оператор видит handoff в canonical reusable execution-pack и decision surfaces

