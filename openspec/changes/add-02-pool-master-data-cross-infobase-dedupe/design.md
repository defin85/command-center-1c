## Context
После already-approved changes у системы появляется два новых orchestration path:
- batch collection reference layer по нескольким ИБ;
- batch rollout/manual sync launch по нескольким ИБ.

Оба change сознательно не решают центральную проблему source-of-truth: как одинаковые бизнес-сущности из разных ИБ превращаются в один canonical reusable object без silent merge и без ручной чистки duplicates постфактум.

Текущий hub already owns:
- canonical entity families (`Party`, `Item`, `Contract`, `TaxProfile`, `GLAccount`, `GLAccountSet`);
- per-infobase bindings;
- pre-publication gate и fail-closed diagnostics;
- registry-driven capabilities.

Но он ещё не описывает отдельный cross-infobase resolution layer, который:
- хранит source evidence до canonical promotion;
- применяет entity-specific semantic matching;
- выбирает deterministic canonical survivor;
- переводит ambiguous clusters в operator review;
- блокирует rollout/publication, пока source-of-truth не стабилизирован.

Именно этот слой и является missing contract между "мы собрали данные из всех ИБ" и "мы можем безопасно считать canonical hub единым reference source".

## Goals / Non-Goals

### Goals
- Ввести явный source-of-truth contract для automatic cross-infobase semantic dedupe.
- Сохранить provenance по каждому источнику, а не терять его после canonical upsert.
- Дать deterministic auto-resolution только там, где match policy это разрешает.
- В ambiguous cases переводить cluster в explicit review queue и блокировать source-of-truth consumption.
- Сделать dedupe operator-visible через `/pools/master-data`.
- Сохранить совместимость с уже существующими collection, bindings, publication и sync contracts.

### Non-Goals
- Не строить "идеальный" universal fuzzy matcher для всех справочников и конфигураций.
- Не заменять registry-driven capabilities на hardcoded heuristics в UI.
- Не превращать `PoolMasterDataBinding` в cross-infobase identity storage.
- Не обещать automatic dedupe для всех entity families в `V1`.
- Не делать отдельный parallel master-data domain вне текущего pool hub.

## Decisions

### Decision: Вводим отдельный source-record / resolution layer перед canonical promotion
Collection и inbound ingress не должны сразу слепо мутировать canonical rows как единственный persisted след. Им нужен промежуточный persisted слой, который хранит:
- source database;
- source object reference/fingerprint;
- origin batch/job/launch;
- normalized identity signals;
- результат resolution.

Это даёт:
- наблюдаемость, откуда взялась canonical запись;
- возможность повторно прогонять resolution без потери source evidence;
- audit trail для operator review.

Практически это означает отдельные persisted read/write model наподобие:
- `source record`;
- `dedupe cluster`;
- `review item` / `resolution item`.

Названия сущностей могут отличаться, но separation of concerns обязателен.

### Decision: Dedupe policy является registry-driven и entity-specific
Нельзя делать один общий "semantic match" для всех reusable entity families. Система должна определять per entity type:
- допускается ли automatic dedupe вообще;
- какие identity signals нормализуются и сравниваются;
- какие mismatches считаются безопасными, а какие требуют review;
- какой survivor precedence используется;
- можно ли использовать unresolved entity в rollout/publication.

Это естественное продолжение already-shipped registry-driven capability model.

Следствия:
- новый entity type без explicit dedupe capability остаётся fail-closed;
- `GLAccountSet` не auto-dedupe'ится в `V1`;
- exact policy для `Party`, `Item`, `Contract`, `TaxProfile`, `GLAccount` может различаться.

### Decision: Automatic merge допускается только по explicit safe rules
System must not "guess". Automatic merge разрешён только если rule-set для entity type даёт safe resolution.

Примеры safe classes:
- `Party`: совпадение deterministic tax identity и role-compatible normalization;
- `Contract`: owner-scoped match с согласованными owner/number/date signals;
- `TaxProfile`: exact structural equality;
- `GLAccount`: exact compatibility class + account identity match.

Если сигналы конфликтуют или недостаточны, resolution идёт в review queue.

### Decision: Canonical survivor должен быть детерминированным и стабильным
Если новый source record попадает в уже resolved cluster, система обязана переиспользовать existing canonical entity, а не создавать новый canonical row "потому что этот import пришёл раньше/позже".

Если cluster создаётся впервые, survivor selection должен использовать explicit precedence, например:
- existing manually curated canonical entity;
- operator-approved survivor;
- deterministic stable ordering по policy.

Arrival order сам по себе не должен становиться source-of-truth rule.

### Decision: Ambiguous clusters переводятся в review-required state и блокируют source-of-truth consumption
Dedupe не должен silently выбирать одну запись при частичном совпадении и конфликтующих атрибутах.

В ambiguous case система создаёт persisted review item с:
- `entity_type`;
- candidate cluster identifier;
- reason code;
- conflicting fields;
- source records;
- proposed survivor/result, если он есть.

Пока review item не переведён в `resolved_auto` или `resolved_manual`, affected canonical scope нельзя использовать для:
- outbound rollout/manual sync launch;
- publication master-data gate;
- automatic source-of-truth promotion дальше по pipeline.

### Decision: UI остаётся внутри `/pools/master-data`, но получает отдельную зону `Dedupe Review`
Эта функциональность тесно связана с canonical hub, bindings и bootstrap/sync surfaces. Отдельный route не нужен.

Внутри `/pools/master-data` появляется отдельная зона:
- очередь `pending_review` и resolution history;
- detail по source provenance и match signals;
- explicit actions: `accept merge`, `choose survivor`, `mark distinct`.

Так оператор остаётся внутри одного workspace и может перейти от collection/sync blocker к фактическому разрешению source-of-truth.

### Decision: Rollout и automatic outbound path потребляют только dedupe-resolved canonical state
Новый dedupe layer не должен жить отдельно от runtime decisions. Его resolution state обязан использоваться:
- automatic outbound outbox fan-out;
- operator manual sync launches;
- publication/readiness gate.

Это не значит, что sync runtime сам реализует dedupe. Он лишь проверяет ready/not-ready status source-of-truth и fail-closed блокирует side effects, если canonical entity ещё не разрешена.

## Alternatives Considered

### Alternative: Оставить dedupe имплицитным внутри current canonical upsert
Отклонено.

Минусы:
- нет persisted source evidence;
- нет operator-visible review surface;
- невозможно доказуемо различить safe auto-merge и случайное overwrite arrival order.

### Alternative: Делать только manual review без automatic dedupe
Отклонено.

Минусы:
- cluster-wide collection быстро превращается в неприемлемый operator backlog;
- система не использует deterministic safe cases, которые можно сводить автоматически.

### Alternative: Использовать `ib_ref_key`/binding rows как global identity
Отклонено.

Это противоречит already-shipped contract: `Ref_Key` target-local и не является canonical или cross-infobase identity.

## Risks / Trade-offs
- Ложноположительный merge повредит canonical layer сильнее, чем ложный negative.
  - Поэтому `V1` должен быть bias-to-review, а не bias-to-merge.
- Появляется ещё один persisted read-model рядом с canonical entities и bindings.
  - Это оправдано, потому что source evidence и canonical source-of-truth — не одно и то же.
- Operator review queue может расти на слабых policy.
  - Это сигнал улучшать entity-specific rules, а не повод разрешать silent merge.
- Rollout/publication blockers станут встречаться чаще сразу после включения feature.
  - Это ожидаемо: система перестанет скрывать unresolved source-of-truth ambiguity.

## Verification Gates
- Safe auto-match из разных ИБ переиспользует один canonical entity и сохраняет provenance обоих источников.
- Missing dedupe capability не приводит к implicit auto-merge.
- Ambiguous cluster создаёт review-required item вместо silent merge.
- Outbound/manual rollout и publication gate блокируются для unresolved dedupe cluster с machine-readable reason.
- UI позволяет увидеть source provenance, conflicting fields и выполнить explicit resolution action.
- Generated contracts и API response shapes синхронизированы с new read-model/actions.
