## Context
Существующий контракт `pool-distribution-runs` фиксирует lifecycle `PoolRun`, direction-specific input и run-local report для расчёта/публикации. Это покрывает execution path, но не закрывает целевой операторский сценарий:

- бухгалтер получает внешний реестр поступлений;
- выбирает стартовую "подушку" вручную;
- запускает распределение суммы по topology;
- позже создаёт реестр реализаций, который выравнивает factual balance на leaf-узлах;
- ожидает увидеть по всем ИБ minute-scale актуальную картину, где суммы зависли и что переносится в следующий квартал.

Главный архитектурный разрыв состоит в том, что текущий run report описывает расчётный runtime артефакт, а пользователю нужен factual balance, построенный по реальным документам и регистрам ИБ, в том числе после ручных действий в 1С.

## Goals
- Ввести canonical batch intake для внешних реестров поступлений и реализаций.
- Поддержать запуск top-down run от явной стартовой организации без жёсткой привязки к одной "подушке".
- Материализовать factual balance projection по `pool / organization / edge / quarter / batch`.
- Держать в projection три денежные меры: `amount_with_vat`, `amount_without_vat`, `vat_amount`.
- Показывать бухгалтеру near-real-time summary/drill-down с явной индикацией, где сумма застряла.
- Отделить batch settlement status от технического lifecycle `PoolRun.status`.
- Поддержать quarter carry-forward на том же узле.

## Non-Goals
- Не меняем фиксированный lifecycle `PoolRun.status`; settlement status вводится отдельно.
- Не пытаемся автоматически исправлять ручные расхождения в 1С.
- Не требуем в первой итерации точной line-level связи между реализацией и исходной строкой прихода.
- Не требуем backfill для исторических batch/run до включения change.
- Не вводим в первой итерации отдельный extension register/change-log для read path; если bounded direct reads из бухгалтерских источников не выдержат rollout budget, это будет follow-up change.
- Не вводим отдельный factual microservice, новый primary runtime или отдельное frontend-приложение для factual monitoring в рамках этого change.

## Chosen Architecture Variant
Целевой вариант для этого change — `B`: расширение существующих runtime boundaries без выделения нового top-level сервиса.

- `orchestrator` владеет доменными контрактами `PoolBatch`, batch settlement lifecycle, factual projection, review queue и public API/read-model surface;
- `worker` остаётся текущим execution runtime family, но получает отдельные operational роли `write` и `read/reconcile` без появления нового primary runtime;
- `frontend` остаётся существующим SPA; factual monitoring открывается как отдельный route/workspace внутри него, а не как новый frontend app;
- canonical call graph не меняется: `frontend -> api-gateway -> orchestrator -> worker -> 1C`;
- execution snapshots (`runtime_projection_snapshot`, `publication_summary`, `PoolPublicationAttempt`) остаются execution lineage/diagnostics и не становятся factual source-of-truth.
- change декомпозируется на три изолированные подсистемы внутри этих же runtime boundaries: `intake`, `factual read/projection`, `reconcile/review`.

## Implementation Readiness
Audit verdict: `Ready with conditions`.

Change готов к implementation phase при соблюдении следующих обязательных условий:

- public/domain contracts для `PoolBatch`, batch-backed `top_down`, factual read-model/API surface и grammar `CCPOOL:v=1;...` фиксируются до начала кодинга runtime и UI;
- factual read model, batch settlement lifecycle, checkpoints и review queue реализуются как отдельный `orchestrator`-owned persistence/API boundary и не встраиваются в existing execution store `PoolRun`;
- pilot/prefight cohort ИБ подтверждает доступность published 1C integration surfaces, достаточных для bounded factual sync, без прямого DB access как primary production path;
- factual `read/reconcile` jobs переиспользуют existing worker scheduling/fairness primitives (`role`, `priority`, `server_affinity`) и rollout envelope этого change, а не вводят новый primary runtime path;
- `/pools/runs` остаётся execution-centric surface; factual monitoring и manual review открываются как отдельный workspace с явной ссылкой из run-local отчёта.

Если хотя бы одно из этих условий нарушается, change должен считаться `Not ready` для implementation до отдельного архитектурного решения или обновления OpenSpec.

## Decisions

### Decision: Вариант B фиксируется как обязательная архитектурная граница change
Этот change НЕ ДОЛЖЕН (SHALL NOT) разрастаться в отдельный factual service или второй primary runtime. Все новые batch/projection/review surfaces реализуются внутри текущих `orchestrator + worker` boundaries.

Это решение выбрано, потому что:

- текущий execution path уже проходит через `orchestrator -> worker -> 1C`;
- `orchestrator` уже владеет tenant-aware domain persistence и public contract boundary;
- отдельный service в первой итерации добавил бы лишний consistency, rollout и observability overhead без обязательной продуктовой выгоды.

### Decision: Вариант B реализуется тремя изолированными подсистемами
Внутри текущих `orchestrator + worker + frontend` boundaries change ДОЛЖЕН (SHALL) быть разложен на три подсистемы с явным ownership и минимальными пересечениями ответственности.

`Intake subsystem`
- отвечает за canonical `PoolBatch`, schema-driven нормализацию, provenance, fail-closed validation и batch-backed create-run kickoff;
- использует существующий execution path для запуска `PoolRun`, но не владеет factual totals, settlement summary и review queue;
- публикует только batch/run lineage и marker-ready provenance, достаточные для downstream attribution.

`Factual read/projection subsystem`
- отвечает за bounded чтение published 1C surfaces, freshness/staleness tracking и materialization factual projection / batch settlement read model;
- использует отдельный `read` lane worker runtime family и не выполняет create-run, schema normalization или operator review actions;
- пишет только в `orchestrator`-owned projection/checkpoint/store boundary и не переиспользует execution snapshots как aggregate store.

`Reconcile/review subsystem`
- отвечает за `unattributed`, `late correction`, operator actions `attribute`, `reconcile`, `resolve_without_change` и audit trail урегулирования;
- не запускает distribution run, не пересчитывает silently историю и не подменяет worker read sync;
- использует отдельный factual workspace внутри существующего SPA и не конкурирует с `/pools/runs` как primary execution canvas.

Граничные правила между подсистемами:
- деградация `factual read/projection` или `reconcile/review` ДОЛЖНА (SHALL) проявляться через staleness/backlog/attention signals, а не через скрытое отключение `intake`;
- `intake` не пишет factual balances напрямую;
- `reconcile/review` не обходит factual projection и не меняет `PoolRun.status`;
- отдельный top-level service, отдельный frontend app или вторая primary queue topology для этих подсистем в рамках change не вводятся.

### Decision: Разделить batch settlement и run execution
`PoolRun` остаётся execution сущностью с текущим FSM (`draft -> validated -> publishing -> partial_success|published|failed`). Для бизнес-статуса баланса вводится отдельная batch/projection сущность со status/read-model уровня:

- `ingested`
- `distributed`
- `partially_closed`
- `closed`
- `carried_forward`
- `attention_required`

Это позволяет не ломать существующий facade contract и одновременно показать пользователю реальную степень закрытия суммы.

Batch/projection слой остаётся внутри pool-domain change и использует вариант `B`: хранение, API и operator-facing read model живут в `orchestrator`-owned boundary, а factual sync/reconcile использует отдельный `read` lane текущего worker runtime family. Execution read model `PoolRun` и factual read model не смешиваются.

### Decision: Source of truth для factual balance это реальные документы и регистры ИБ
Баланс не должен считаться по ожидаемым суммам из distribution artifact. Projection строится по фактическим данным ИБ:

- документам, созданным через Command Center;
- движениям/регистрам, влияющим на баланс;
- ручным документам пользователя, если они видны в ИБ.

В первой итерации бухгалтерским эталоном считается отчёт `Продажи`, построенный на bounded чтении источников:

- `РегистрБухгалтерии.Хозрасчетный.Обороты(...)`;
- `РегистрСведений.ДанныеПервичныхДокументов`;
- связанных документов `РеализацияТоваровУслуг`, `ВозвратТоваровОтПокупателя`, `КорректировкаРеализации`, которые используются в логике отчёта.

Runtime artifacts Command Center остаются provenance-слоем и помогают атрибуции, но не подменяют фактическое состояние.

### Decision: Materialized read model вместо on-demand расчёта
Для 700 ИБ и minute-scale обновления нужен централизованный materialized projection в Command Center. UI не должен пересчитывать баланс прямыми запросами в ИБ. Projection обновляется:

- немедленно после собственных действий Command Center;
- фоновыми `read worker` циклами прямого bounded чтения бухгалтерских источников без отдельного extension/change-log в v1;
- с явной меткой freshness/staleness, если ИБ недоступна или находится в maintenance.

Bounded direct read path в первой итерации фиксируется так:

- читаются только организации, участвующие в активных пулах;
- читается только квартал пула, а для закрытых кварталов используется отдельный reconcile job;
- используются только счета и типы движений, которые участвуют в отчёте `Продажи`;
- unbounded full scan всего регистра как primary sync path не допускается.

Materialized projection хранится в `orchestrator`-owned persistence boundary. Existing execution snapshots и run-local diagnostics не используются как фактический aggregate store.

### Decision: Factual sync использует только поддерживаемые published 1C integration surfaces
В первой итерации `read worker` читает factual slice только через поддерживаемые published integration surfaces 1С:

- standard OData published objects, virtual tables и functions регистров;
- либо явный published HTTP service contract, если конкретный bounded read нельзя безопасно выразить через OData.

Primary production read path не использует прямой доступ к таблицам БД ИБ, ad-hoc SQL и другие unsupported способы чтения. Для каждого source profile фиксируется allowlist publishable objects/functions, а runtime discovery всех доступных metadata objects не используется как основной механизм синхронизации.

### Decision: Traceability v1 через machine-readable комментарий документа
Для документов, созданных через Command Center, traceability в первой итерации фиксируется в начале комментария документа в жёстком формате:

`CCPOOL:v=1;pool=<uuid>;run=<uuid|->;batch=<uuid|->;org=<uuid>;q=<YYYYQn>;kind=<receipt|sale|carry|manual>||<optional human text>`

Правила контракта:

- machine-readable блок всегда идёт в начале комментария;
- используется только ASCII и фиксированный порядок ключей;
- `pool` обязателен и служит primary attribution key, в том числе когда одна организация участвует в нескольких пулах одного квартала;
- всё, что правее `||`, считается произвольным human-readable хвостом и игнорируется парсером;
- отсутствие или непарсибельность блока переводит документ в `unattributed`.

Machine-readable блок формируется на compile/publication path из canonical batch/run provenance и записывается в comment field документа как prefix перед публикацией. При retry/update того же логического документа machine-readable блок должен оставаться стабильным, а human-readable хвост после `||` должен сохраняться без silent rewrite.

Для ручных документов без traceability projection хранит вклад как `unattributed`:

- они влияют на factual totals организации/квартала;
- они не должны silently распределяться по конкретному batch/edge;
- пользователь в первой итерации размечает их вручную.

### Decision: Один внешний batch порождает ровно один pool_run
`one batch = one pool_run` фиксирует traceability и упрощает операторское объяснение: бухгалтер видит, какой реестр породил какой run и какие дальнейшие движения/остатки из него выросли.

Для batch-backed `top_down` direction-specific input включает явные `batch_id` и `start_organization_id`. Existing manual `top_down` path со `starting_amount` сохраняется как отдельный operator-facing режим и не подменяется batch contract.

Idempotency fingerprint для batch-backed create-run обязан различать как минимум:

- `batch_id`;
- `start_organization_id`;
- accounting period batch/run;
- `pool_workflow_binding_id`;
- pinned `binding_profile_revision_id`;
- canonicalized batch-backed run input.

Повторный submit того же batch-backed запроса должен reuse'ить тот же `PoolRun`, а не создавать дубликат.

### Decision: Реализации закрывают баланс агрегатно, а не line-by-line
В первом релизе фактическая реализация выравнивает накопленный баланс на узле/квартале без требования прямой связи с исходной строкой прихода. Для продажи из batch intake обязателен leaf-node scope; поддержка промежуточных узлов остаётся follow-up.

Измерение `edge` в projection при этом сохраняется как derived read model: leaf-scoped sale уменьшает открытые attributed incoming balances leaf-узла детерминированно, oldest-first, без обязательного line-level pairing receipt rows. Отдельная бухгалтерская "продажа по ребру" как source of truth в первой итерации не вводится.

### Decision: Quarter carry-forward считается на том же узле
Остаток, дошедший до leaf-узла и не закрытый фактическими реализациями, переносится в следующий квартал на том же узле. Возврат суммы "назад" по цепочке вне явной продажи в рамках этого change не поддерживается.

### Decision: Поздние корректировки после фиксации пула НЕ пересчитывают историю автоматически
После того как по `pool + quarter` рассчитан и зафиксирован carry-forward, квартал считается frozen для автоматического пересчёта.

Если `read worker` обнаруживает документ или изменение, влияющее на уже зафиксированный квартал:

- historical factual balance за закрытый квартал не пересчитывается silently;
- carry-forward следующего квартала не меняется silently;
- формируется `attention_required` сигнал и operator-facing элемент для manual reconcile.

Первая итерация допускает только ручное урегулирование таких случаев пользователем.

Manual review queue для `unattributed` и `late correction` живёт отдельно от batch settlement status. Review item хранит reason, source document reference, affected scope, delta snapshot и operator audit trail. В первой итерации допустимы только явные operator actions `attribute`, `reconcile` и `resolve_without_change`; автоматическое скрытое урегулирование не допускается.

### Decision: Operator-facing factual context отделяется от run-local execution canvas
`/pools/runs` сохраняет execution-centric UX: create, inspect, safe actions, retry и run-local report. Factual monitoring и manual review должны открываться как отдельный factual context surface, связанный с run/batch lineage, а не как ещё один тяжёлый primary pane внутри того же execution canvas.

Первая итерация использует вариант `B`: отдельный factual route/workspace внутри существующего frontend приложения без отдельного frontend app или backend service. Execution controls и factual settlement/review не должны конкурировать как единое primary content.

### Decision: Rollout envelope для 700 ИБ фиксируется отдельными read/write workers и жёсткими лимитами
Первая итерация разделяет operational роли:

- `write workers` публикуют документы в ИБ;
- `read workers` только читают бухгалтерские источники и обновляют projection.

Под `write workers` и `read workers` здесь понимаются отдельные process roles / lanes внутри текущего worker runtime family, а не новый standalone microservice.

Стартовый rollout envelope:

- не более одного одновременного read job на одну ИБ;
- не более двух одновременных read jobs на один кластер 1С;
- глобальный стартовый лимит `8` read jobs;
- polling tiers: `120 сек` для active pool/quarter, `10 мин` для warm, `60 мин` для cold;
- для закрытых кварталов используется отдельный ночной reconcile job.

## Alternatives Considered

### Рассчитывать dashboard только по run artifacts
Отклонено. Такой подход ломается сразу после ручных действий пользователя в 1С и не даёт factual picture.

### Расширить `PoolRun.status` settlement-статусами
Отклонено. Это смешивает execution lifecycle с бизнес-закрытием баланса и конфликтует с уже зафиксированным контрактом `pool-distribution-runs`.

### Автоматически распределять manual realizations между пулами
Отклонено для первой итерации. В v1 attribution выполняется только по machine-readable `pool` marker в комментарии, а всё, что не матчится однозначно, попадает в `unattributed`.

### Вводить extension register/change-log сразу в первой итерации
Отклонено. Для v1 выбран bounded direct read из бухгалтерских источников, на которых построен отчёт `Продажи`, чтобы не расширять rollout surface до стабилизации нагрузки.

### Выделить отдельный factual microservice
Отклонено. Для v1 это создаёт новый runtime boundary, усложняет consistency между execution и factual слоями и не даёт обязательного выигрыша по продукту или operability по сравнению с вариантом `B`.

## Risks / Trade-offs
- Bounded direct read из бухгалтерских источников всё ещё создаёт риск по throughput и freshness на 700 ИБ; rollout зависит от жёстких caps, sharding и backpressure.
- Комментарий как traceability surface уязвим к ручной порче формата; это увеличит объём `unattributed`, но лучше, чем silently искажать pool/batch attribution.
- Initial leaf-only settlement не закрывает будущий сценарий продаж на промежуточных узлах; это нужно учитывать в data model, чтобы не блокировать расширение.
- Late corrections после фиксации квартала переносят нагрузку на операторов manual reconcile, но это безопаснее, чем автоматический пересчёт уже зафиксированной истории.
- Если production read path будет реализован через прямой доступ к таблицам БД ИБ вместо published 1C integration surfaces, change потеряет upgrade-safety и operability; такой путь не считается допустимым primary architecture choice для v1.

## Migration Plan
1. Сначала ввести `intake subsystem` contracts: canonical `PoolBatch`, batch-backed create-run contract, idempotency fingerprint и marker-ready provenance без изменения существующего `PoolRun` lifecycle.
2. Затем ввести `factual read/projection subsystem`: checkpoints, materialized projection, batch settlement read model и bounded direct reads через `read` lane текущего worker runtime family.
3. После этого подключить `reconcile/review subsystem`: separate factual context, `unattributed`/`late correction` queue и operator actions внутри существующего frontend приложения.
4. Добавить machine-readable comment marker для новых документов, создаваемых Command Center, и связать его с downstream attribution/review policy.
5. Включить rollout caps/telemetry для независимого контроля `write` и `read/reconcile` lanes.
6. Если rollout telemetry покажет, что bounded direct reads не укладываются в budget, вынести отдельным change dedicated change-log/outbox surface, не ломая границы трёх подсистем.

## Open Questions
Блокирующих открытых вопросов на уровне change не осталось. Допускается только operational tuning лимитов polling/read workers внутри зафиксированного rollout envelope.
