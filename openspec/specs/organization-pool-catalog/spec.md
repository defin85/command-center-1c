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

### Requirement: Topology API MUST сохранять и возвращать metadata, достаточную для document-policy управления
Система ДОЛЖНА (SHALL) в mutating topology snapshot API сохранять `node.metadata` и `edge.metadata` без потери данных, включая `edge.metadata.document_policy`.

Система ДОЛЖНА (SHALL) в read-path topology/graph API возвращать metadata узлов и рёбер, чтобы оператор мог безопасно редактировать document-policy без внешних инструментов.

#### Scenario: Оператор сохраняет document-policy в edge metadata и видит его в read-path
- **GIVEN** оператор отправляет topology snapshot с `edge.metadata.document_policy`
- **WHEN** snapshot сохраняется и затем читается через graph/topology endpoint
- **THEN** response содержит сохранённое `edge.metadata.document_policy`
- **AND** оператор может выполнить повторное редактирование без потери metadata

### Requirement: Topology document-policy mutating MUST валидироваться fail-closed до persistence
Система ДОЛЖНА (SHALL) валидировать `edge.metadata.document_policy` на соответствие contract version (`document_policy.v1`) в момент topology mutating запроса.

Система НЕ ДОЛЖНА (SHALL NOT) сохранять snapshot с невалидной policy.

#### Scenario: Невалидная policy отклоняется на этапе topology upsert
- **GIVEN** оператор отправляет snapshot с `document_policy`, нарушающим contract schema
- **WHEN** backend выполняет pre-persist validation
- **THEN** запрос отклоняется валидационной ошибкой
- **AND** topology snapshot в БД остаётся неизменным

### Requirement: Topology metadata contract MUST быть schema-stable для API и клиента
Система ДОЛЖНА (SHALL) публиковать в topology/graph API явные поля `node.metadata` и `edge.metadata` как часть стабильного read-model контракта, включая `edge.metadata.document_policy`.

Система ДОЛЖНА (SHALL) сохранять round-trip совместимость metadata: пользовательские поля metadata не теряются между mutating и последующим read-path вызовом.

#### Scenario: Round-trip topology metadata не теряет пользовательские поля
- **GIVEN** snapshot содержит `node.metadata`, `edge.metadata` и валидный `edge.metadata.document_policy`
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

### Requirement: Topology editor UI MUST поддерживать интерактивное создание Document policy и Edge metadata
Система ДОЛЖНА (SHALL) предоставлять в `/pools/catalog` topology editor для structural `node.metadata` / `edge.metadata` и explicit compatibility path для legacy `edge.metadata.document_policy`.

После поставки replacement decision-resource authoring UI topology editor НЕ ДОЛЖЕН (SHALL NOT) оставаться primary surface для net-new `document_policy` authoring.

Для legacy edge `document_policy` UI ДОЛЖЕН (SHALL):
- показывать existing policy read-only по умолчанию;
- требовать явное compatibility/migration действие для открытия legacy editor;
- предоставлять explicit compatibility shortcut/handoff к canonical import surface на `/decisions` и к тому же migration contract для decision resource + selected binding refs;
- показывать migration provenance и целевые refs после успешного импорта.

#### Scenario: Оператор запускает compatibility shortcut из `/pools/catalog` для legacy edge policy
- **GIVEN** topology edge содержит legacy `document_policy`
- **AND** для пула существует workflow-centric binding
- **WHEN** оператор запускает explicit compatibility action из `/pools/catalog`
- **THEN** UI использует тот же deterministic migration contract, что и canonical import surface на `/decisions`
- **AND** topology editor показывает migration outcome и направляет оператора на decision-resource lifecycle вместо продолжения direct edge authoring как primary path

#### Scenario: Новый topology edge не навязывает direct document_policy authoring
- **GIVEN** оператор добавляет новый edge в topology editor
- **WHEN** UI рендерит controls для edge metadata
- **THEN** structural metadata остаётся доступной
- **AND** primary guidance направляет автора на route `/decisions` для net-new `document_policy`

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

### Requirement: Topology mutating validation MUST проверять соответствие policy актуальному metadata catalog
Система ДОЛЖНА (SHALL) при сохранении topology snapshot валидировать, что ссылки в `document_policy` указывают на существующие элементы current metadata snapshot выбранной ИБ/конфигурации:
- `entity_name`;
- `field_mapping` ключи;
- `table_parts_mapping` и `row_fields`.

Система НЕ ДОЛЖНА (SHALL NOT) сохранять snapshot, если policy ссылается на отсутствующие документы/поля/табличные части.
Система НЕ ДОЛЖНА (SHALL NOT) сохранять snapshot, если для выбранной ИБ/конфигурации отсутствует current metadata snapshot.

Ответ об ошибке ДОЛЖЕН (SHALL) использовать единый формат `code + path + detail` для referential validation.

Для нарушений ссылок policy на metadata система ДОЛЖНА (SHALL) возвращать `code=POOL_METADATA_REFERENCE_INVALID`.
При отсутствии current metadata snapshot система ДОЛЖНА (SHALL) возвращать `code=POOL_METADATA_SNAPSHOT_UNAVAILABLE`.

#### Scenario: Policy с несуществующим реквизитом отклоняется до persistence
- **GIVEN** оператор сформировал policy с `field_mapping`, где указан несуществующий реквизит документа
- **WHEN** выполняется topology snapshot save
- **THEN** backend отклоняет запрос валидационной ошибкой
- **AND** snapshot в БД не изменяется
- **AND** UI получает `code`, `path`, `detail` для подсветки проблемного поля

#### Scenario: Сохранение topology блокируется при отсутствии current metadata snapshot
- **GIVEN** для выбранной ИБ/конфигурации нет актуального metadata snapshot
- **WHEN** выполняется topology snapshot save
- **THEN** backend отклоняет запрос fail-closed ошибкой
- **AND** UI получает `code=POOL_METADATA_SNAPSHOT_UNAVAILABLE` и `path` проблемного policy context

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
Система ДОЛЖНА (SHALL) управлять workflow bindings на `/pools/catalog` через dedicated binding workspace и dedicated binding endpoints, backed by the same canonical store, который использует runtime resolution.

Pool upsert contract НЕ ДОЛЖЕН (SHALL NOT) нести canonical binding payload и НЕ ДОЛЖЕН (SHALL NOT) переписывать binding state как side effect редактирования базовых полей пула.

Binding read path ДОЛЖЕН (SHALL) возвращать server-managed `revision` для compatibility single-binding operations и lineage visibility.

UI ДОЛЖЕН (SHALL) разделять:
- mutating операции над базовыми полями `pool`;
- mutating операции над `pool_workflow_binding`.

Для default multi-binding save UI ДОЛЖЕН (SHALL) использовать публичный collection-level atomic save contract `PUT /api/v2/pools/workflow-bindings/` поверх canonical binding store и НЕ ДОЛЖЕН (SHALL NOT) полагаться на последовательность client-side `upsert/delete`, которая допускает partial apply.

Default collection-save UI ДОЛЖЕН (SHALL) использовать `collection_etag` / `expected_collection_etag` как единственный workspace concurrency contract. Per-binding `revision` НЕ ДОЛЖЕН (SHALL NOT) использоваться как primary conflict token для default multi-binding save.

При collection conflict UI ДОЛЖЕН (SHALL) сохранять введённые данные формы, показывать причину конфликта и предлагать reload canonical collection без потери локального edit state.

#### Scenario: Сохранение базовых полей пула не переписывает workflow bindings
- **GIVEN** оператор редактирует `code` или `name` пула в `/pools/catalog`
- **AND** у пула уже есть active workflow bindings
- **WHEN** оператор сохраняет только базовые поля пула
- **THEN** UI использует pool upsert path без canonical binding payload
- **AND** существующие workflow bindings не теряются и не переписываются

#### Scenario: Binding editor использует тот же canonical CRUD, что и runtime
- **GIVEN** оператор добавляет или удаляет workflow binding в `/pools/catalog`
- **WHEN** изменение сохраняется
- **THEN** UI читает и сохраняет canonical collection через `GET/PUT /api/v2/pools/workflow-bindings/`
- **AND** следующий create-run/read-model видит это же изменение без дополнительного metadata sync шага

#### Scenario: Stale collection etag в catalog editor возвращает conflict без потери формы
- **GIVEN** оператор редактирует workflow bindings в `/pools/catalog`
- **AND** другой оператор уже сохранил новую canonical collection
- **WHEN** первый оператор пытается отправить состояние со старым `expected_collection_etag`
- **THEN** backend возвращает machine-readable conflict по `expected_collection_etag`
- **AND** UI сохраняет введённые данные для повторной попытки

#### Scenario: Workspace-save не оставляет частично применённые bindings
- **GIVEN** оператор меняет набор bindings в isolated workspace
- **AND** один из элементов запроса конфликтует с более новой canonical collection
- **WHEN** UI отправляет multi-binding save
- **THEN** backend отклоняет весь save как единый conflict
- **AND** после reload оператор видит либо старую целую canonical collection, либо полностью новую, но не partial mix обоих состояний

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

