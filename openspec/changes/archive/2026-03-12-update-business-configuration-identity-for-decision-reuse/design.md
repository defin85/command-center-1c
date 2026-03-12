## Context
Сейчас система использует configuration-scoped metadata snapshot contract, в котором identity фактически строится из:
- `config_name`;
- `config_version`;
- `extensions_fingerprint`;
- `metadata_hash`.

В коде `config_name` вычисляется из `database.base_name || database.infobase_name || database.name`, а `config_version` из `Database.version`. Это хорошо работает как database-local heuristic, но не как бизнес-идентичность прикладного решения.

Одновременно `metadata_hash` считается от опубликованного OData payload. По документам 1C published OData composition определяется publication settings и `SetStandardODataInterfaceContent`, то есть зависит от operational publication state, а не только от версии конфигурации.

Проверка на живой выгрузке БП 3.0 подтвердила, что root `Configuration.xml` уже содержит нужные business properties:
- `Name`
- `Synonym`
- `Vendor`
- `Version`

Это и есть корректный source-of-truth для business identity конфигурации.

Одновременно практическая проверка acquisition paths показала:
- RAS/rac в текущем окружении не дают `configuration name/version` и для infobase details требуют cluster admin rights;
- `Designer` batch mode на Linux в текущем runtime упирается в GTK/X11 и не подходит как дешёвый headless probe;
- прямой SQL в PostgreSQL даёт только внутренние blobs/technical tables (`config`, `params`, `ibversion`) и не образует поддерживаемый business contract;
- `ibcmd config generation-id` работает быстро и headless, но даёт только technical equal/not-equal marker;
- `ibcmd infobase config export objects Configuration` работает headless, выгружает `Configuration.xml` с нужными `Name/Synonym/Vendor/Version`, и в живой проверке занял около 34 секунд и ~10 MB на базу;
- полный `ibcmd config export` operationally слишком тяжёлый для массового runtime use и в живой пробе быстро ушёл в сотни мегабайт.
- В уже shipped UI `Command Schemas` (`/settings/command-schemas?driver=ibcmd&mode=guided`) в approved base catalog уже присутствуют нужные schema-driven commands:
  - `infobase.config.generation-id`;
  - `infobase.config.export.objects`.
- В already shipped runtime публичный path `POST /api/v2/operations/execute-ibcmd-cli/` уже резолвит `command_id` через driver catalog, а workflow backend `ibcmd_cli` уже маршрутизирует эти операции в Go worker driver.

Следовательно, business identity должна определяться root configuration properties по смыслу, но извлекаться runtime'ом profile-driven способом, а не через full dump или Designer probe на каждый refresh.
Дополнительное архитектурное ограничение этого change: extraction path не должен создавать второй параллельный runtime для `ibcmd`; он должен переиспользовать уже существующую execution chain `workflow/operations -> worker -> driver`, где `ibcmd_cli` является единственным публичным IBCMD executor.

## Goals
- Использовать business identity конфигурации как compatibility/reuse key для shared metadata snapshots и `decision_revision`.
- Получать identity по смыслу из root configuration properties, но runtime'ом использовать persisted business profile с асинхронной верификацией/заполнением.
- Убрать зависимость reuse от имени ИБ.
- Перевести `metadata_hash` и связанные operational markers в diagnostics/provenance слой.
- Сохранить analyst-facing reuse `decision_revision` между ИБ одной и той же конфигурации даже при publication drift.
- Не требовать full configuration dump или Designer/X11 path в hot path metadata refresh для 700+ ИБ.
- Переиспользовать существующий execution contract `workflow/operations -> worker -> driver` и не плодить второй путь исполнения `ibcmd`.
- Переиспользовать уже существующие guided command schemas `infobase.config.generation-id` и `infobase.config.export.objects`, а не проектировать новый каталог команд ради этой возможности.

## Non-Goals
- Не определять в этом change полный support workflow исправления OData publication у tenant.
- Не использовать `metadata_hash`, `config_generation_id` или `extensions_fingerprint` как новые blocking compatibility keys.
- Не вводить dependence на OData как источник business identity конфигурации.
- Не делать `ibcmd infobase config export objects Configuration` синхронной обязательной операцией на каждый metadata refresh.
- Не добавлять direct shell executor в orchestrator или отдельный background runner, обходящий worker/driver pipeline.
- Не расширять scope change на изобретение новых `ibcmd` command ids, если нужные schema ids уже присутствуют в approved catalog.
- Не менять route structure `/decisions` или `/pools/catalog` вне identity/provenance semantics.

## Decision 1: Business identity конфигурации равна `config_name + config_version`
Нормативная configuration identity для metadata snapshot reuse и compatibility `decision_revision` фиксируется как:
- `config_name`
- `config_version`

Под `config_name` в этом change понимается business-level имя конфигурации, а не имя ИБ.

Имя ИБ, `database_id`, `metadata_hash`, `extensions_fingerprint` и `config_generation_id` НЕ ДОЛЖНЫ (SHALL NOT) участвовать в reuse/compatibility key.

## Decision 2: Источник истины для смысла identity только root configuration properties
Нормативный смысл business identity должен определяться только root configuration properties.

Минимальный нормативный source-of-truth:
- `config_name`: root configuration `Synonym` в предпочтительной локали `ru`; если подходящий `Synonym` отсутствует, допускается fallback к первому доступному synonym entry; если synonym недоступен, допускается fallback к root `Name`.
- `config_version`: root configuration `Version`.

Система не должна:
- брать `config_name` из `Database.base_name`, `Database.infobase_name` или `Database.name`;
- брать `config_version` из `Database.version`;
- выводить business identity из OData payload;
- подменять её `config_generation_id`.

Причина: именно root configuration properties соответствуют тому, что 1C считает application properties/release details.

## Decision 3: Runtime acquisition идёт через persisted business profile, а не через heavy probe на каждый refresh
Runtime path должен использовать persisted business profile, сохранённый в metadata snapshot/read-model или связанной persisted projection.

Нормативный acquisition contract:
- metadata refresh/read path по умолчанию читает уже сохранённые `config_name`, `config_version` и supporting provenance из persisted profile;
- если persisted profile отсутствует, помечен как stale или требует верификации после обновления ИБ, система ДОЛЖНА (SHALL) запускать асинхронный probe job;
- этот probe job ДОЛЖЕН (SHALL) использовать существующую execution chain `workflow/operations -> worker -> driver`;
- standalone acquisition job ДОЛЖЕН (SHALL) materialize'иться как operation/command execution с executor `ibcmd_cli`, а не как direct shell invocation из orchestrator;
- standalone acquisition job ДОЛЖЕН (SHALL) использовать уже существующий публичный path `POST /api/v2/operations/execute-ibcmd-cli/` или эквивалентный operation template / workflow step, который в итоге вызывает тот же `ibcmd_cli` executor;
- если acquisition является частью большего maintenance flow, он ДОЛЖЕН (SHALL) встраиваться как workflow step, который в итоге использует тот же `ibcmd_cli` execution path;
- default headless extraction command в этом execution path ДОЛЖЕН (SHALL) использовать existing schema-driven `command_id = infobase.config.export.objects` c root object selector `Configuration`;
- probe job ДОЛЖЕН (SHALL) парсить `Configuration.xml` и сохранять как минимум `Name`, `Synonym`, `Vendor`, `Version`;
- результат worker execution ДОЛЖЕН (SHALL) возвращать artifact/provenance, достаточный для парсинга `Configuration.xml` и обновления persisted business profile;
- hot path metadata refresh НЕ ДОЛЖЕН (SHALL NOT) требовать полного `DumpConfigToFiles`, полного `ibcmd config export`, Designer/X11 invocation или обхода worker/driver chain для каждой ИБ.

Следствие: runtime дешёв по умолчанию, а heavy extraction выполняется только как bootstrap/backfill/on-change job.

## Decision 4: `config_generation_id` используется только как cheap change-detection marker
Existing schema-driven `command_id = infobase.config.generation-id` ДОЛЖЕН (SHALL) использоваться только как technical marker:
- чтобы понять, менялась ли конфигурация данной ИБ с момента последней верификации business profile;
- чтобы решать, нужен ли повторный async extraction job;
- чтобы хранить provenance для diagnostics/audit.

В operational architecture этот probe также ДОЛЖЕН (SHALL) идти через существующий `ibcmd_cli` executor и worker/driver chain, а не через прямой вызов платформенной утилиты из orchestrator.

`config_generation_id` НЕ ДОЛЖЕН (SHALL NOT):
- использоваться как cross-infobase business identity;
- становиться частью shared snapshot reuse key;
- заменять `config_version`.

Это соответствует официальной semantics 1C: generation ID имеет смысл сравнивать только как equal/not-equal marker, а не как business release identity.

## Decision 5: `metadata_hash`, `extensions_fingerprint` и `config_generation_id` становятся diagnostics-only markers
Эти markers остаются полезными, но меняют роль:
- `metadata_hash` описывает publication surface;
- `extensions_fingerprint` описывает technical applicability/customization state;
- `config_generation_id` описывает technical metadata generation;
- имя ИБ и provenance database описывают operational source.

Они должны сохраняться и возвращаться в API/read-model, но:
- не участвуют в shared snapshot reuse key;
- не образуют hard incompatibility для `decision_revision`;
- не скрывают compatible revision из default `/decisions` path.

## Decision 6: Publication drift non-blocking для reuse, но остаётся видимой диагностикой
Если две ИБ имеют одинаковые `config_name + config_version`, но разный published OData payload, система должна считать их business-compatible для reuse metadata snapshots и `decision_revision`.

При этом publication drift не должен исчезать:
- read-model должен показывать, что selected infobase diverges от canonical/shared publication state;
- `/decisions` и related selectors должны показывать warning/diagnostics;
- drift не должен переводить revision в incompatible только сам по себе.

Это соответствует business policy: за неполную публикацию отвечает support/operations слой, а не analyst-facing compatibility contract.

## Decision 7: Shared snapshot registry остаётся canonical, но scope становится business-level
Canonical metadata snapshot registry по-прежнему нужен как reusable read-model для builder/preview.

Но теперь canonical scope определяется business identity `config_name + config_version`, а не publication hash.

Практический смысл:
- selected database остаётся auth/probe source и provenance anchor;
- canonical snapshot может быть подтверждён другой ИБ той же конфигурации;
- infobase с неполной publication может использовать canonical snapshot peer-ИБ той же business identity.

## Decision 8: Decision compatibility и selector filtering используют только business identity
`Decision revision` для `document_policy` должна считаться business-compatible, если текущий context и stored context совпадают по `config_name + config_version`.

Следствия:
- разные имена ИБ не должны ломать compatibility;
- разный `metadata_hash` не должен делать revision incompatible;
- `config_generation_id` и `extensions_fingerprint` не должны участвовать в filtering/selectability;
- stored provenance markers остаются в UI/read-model как auditable diagnostics.

## Risks / Trade-offs
- Плюс: analyst-facing reuse соответствует реальному бизнес-ожиданию “одна конфигурация, один релиз”.
- Плюс: исчезает ложная несовместимость из-за имени ИБ.
- Плюс: исчезает ложная несовместимость из-за publication drift.
- Плюс: acquisition path подтверждён на живом runtime без Designer/X11.
- Плюс: reuse существующей `operations -> worker -> driver` цепочки не создаёт второй runtime surface для `ibcmd`.
- Минус: система перестаёт fail-closed блокировать reuse при неидеальной публикации OData.
- Минус: `Synonym` локализован; нужен детерминированный fallback порядок.
- Минус: selective export через `ibcmd` всё ещё не бесплатен; его нужно выносить в async/background path и не делать обязательным для каждого refresh.
- Минус: может потребоваться договорить artifact/result contract для `Configuration.xml` handoff между worker и orchestrator, хотя сами `command_id` уже существуют в current approved catalog.
- Минус: старые snapshots/revisions, сохранённые по legacy semantics, потребуют migration/backfill.

## Migration / Rollout
1. Зафиксировать новый contract в specs и OpenAPI/read-model.
2. Зафиксировать execution boundary: acquisition использует существующий `workflow/operations -> worker -> driver` pipeline.
3. Добавить persisted business profile и async verification/bootstrap path.
4. Добавить cheap `config_generation_id` probe для определения необходимости re-verify.
5. Реализовать selective `ibcmd infobase config export objects Configuration` extraction root properties через `ibcmd_cli`.
6. Зафиксировать reuse существующих schema-driven `command_id` (`infobase.config.generation-id`, `infobase.config.export.objects`) и при необходимости дожать только operation/artifact wiring.
7. Перевести snapshot scope/resolution и decision compatibility на `config_name + config_version`.
8. Сохранить legacy markers как diagnostics-only provenance.
9. Выполнить migration/backfill текущих snapshot/revision metadata contexts на новую semantics.
10. Обновить `/decisions` filtering и rollover flow на новый business compatibility contract.

## Open Questions
- Нет блокирующих. В рамках этого change принимается явное решение пользователя: compatibility/reuse key ограничивается только связкой “конфигурация + её версия”.
