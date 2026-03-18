## Контекст

Текущая модель `pool_workflow_binding` решает две разные задачи одной сущностью:
- reusable схема публикации и slot mapping;
- pool-local lifecycle (`status`, `effective_from/effective_to`, selector scope, explicit runtime selection).

Это удобно для одного пула, но плохо масштабируется на много пулов с повторяющимися схемами:
- одинаковые binding-ы копируются и начинают drift'ить;
- update типовой схемы требует ручного изменения каждого пула;
- shared binding row на несколько пулов создаст высокий blast radius и разрушит pool-local ownership.

Дополнительно proposal сознательно опирается на active change `refactor-topology-document-policy-slots`: reusable profile revision должен содержать slot-oriented decision refs (`decision_key` + `slot_key`), иначе profile reuse снова смешает identity reusable decision и identity binding slot.

Текущий create-run idempotency key уже зависит от `pool_workflow_binding_id`, но пока не различает pool-local attachment revision и pinned reusable profile revision отдельно. Для profile model это становится обязательным архитектурным условием.

## Цели

- Развести reusable analyst-authored схему и pool-local runtime attachment.
- Сохранить explicit `pool_workflow_binding_id` как runtime boundary для preview/create-run/retry.
- Дать аналитику одно место для authoring и versioning типовых схем.
- Дать оператору pool-local control над activation window и selector scope без копирования reusable логики.
- Минимизировать migration risk и не навязывать автоматическое semantic dedupe historical bindings.

## Не-цели

- Не вводить cross-tenant reuse binding profiles в этом change.
- Не вводить attachment-local overrides для workflow/slot map/parameters/role mapping в MVP.
- Не заменять `pool_workflow_binding_id` на `binding_profile_revision_id` в public runtime API.
- Не делать automatic merge/dedup существующих одинаковых bindings между пулами.
- Не менять `/decisions` как canonical authoring surface для reusable `document_policy` revisions.

## Рассмотренные варианты

### 1. Тиражировать binding payload из одного pool в другие

Плюсы:
- минимальные изменения модели;
- легко реализовать bulk-copy.

Минусы:
- drift становится нормой, а не исключением;
- нет общего versioned source-of-truth;
- невозможно безопасно понять, какие binding-ы все еще считаются “одной и той же” типовой схемой.

Вывод: отвергнуто как краткосрочный workaround, а не целевая архитектура.

### 2. Сделать один shared live binding, используемый несколькими pool

Плюсы:
- reuse без копирования;
- update одной записи мгновенно распространяется на много пулов.

Минусы:
- `status`, selector scope и effective period перестают быть pool-local;
- одна ошибка или revision update затрагивает сразу много runtime path;
- audit/read-model становятся менее понятными: трудно отделить reusable схему от факта её активации в конкретном pool.

Вывод: отвергнуто из-за высокого blast radius и смешения ownership boundaries.

### 3. `binding_profile_revision` + `pool attachment`

Плюсы:
- reusable логика versioned и централизована;
- pool-specific lifecycle остаётся локальным;
- runtime boundary сохраняется через explicit attachment id;
- rollout новой profile revision можно делать pool-by-pool.

Минусы:
- появляется новая сущность и ещё один UI/API surface;
- attachment read-model должен подтягивать resolved profile revision.

Вывод: выбранный вариант.

### 4. Переиспользовать схемы только на уровне workflow

Плюсы:
- reuse orchestration graph и subworkflow composition уже частично существует в текущей модели;
- уменьшается число новых доменных сущностей, если считать “схемой” только workflow graph.

Минусы:
- executable схема в текущем runtime включает не только workflow graph, но и slot-oriented decision refs, default parameters, role mapping и pool-local activation scope;
- перенос reusable схемы целиком в workflow definition снова смешает orchestration и binding-specific business packaging;
- если оставить `decisions` / `parameters` / `role_mapping` в attachment, reusable source-of-truth для полной схемы так и не появится;
- runtime boundary, lineage и idempotency уже привязаны к explicit `pool_workflow_binding_id`, а не к workflow revision alone.

Вывод: workflow-level reuse сохраняется как reuse orchestration, но не заменяет `binding_profile_revision` как reusable execution scheme.

## Решение

### 1. Новая reusable сущность: binding profile

Вводятся:
- `binding_profile` как stable business identity (`code`, `name`, tenant scope, lifecycle metadata);
- `binding_profile_revision` как immutable ревизия reusable схемы;
- opaque `binding_profile_revision_id` как единственный runtime pin на конкретную immutable revision;
- monotonic `revision_number` как operator-facing/read-model поле, не используемое вместо immutable pin.

`binding_profile_revision` хранит:
- pinned workflow revision;
- slot-oriented decision refs;
- default parameters;
- role mapping;
- optional descriptive metadata/provenance.

Именно profile revision является reusable source-of-truth для логики схемы.

### 1.1 Границы ответственности: workflow != profile != attachment

`workflow definition` остаётся reusable библиотекой orchestration graph и subworkflow composition. Он НЕ ДОЛЖЕН становиться единственным reusable контейнером полной исполняемой схемы пула в рамках этого change.

`binding_profile_revision` хранит reusable execution scheme поверх workflow revision:
- pinned workflow revision;
- publication slot refs;
- default parameters;
- role mapping.

`pool_workflow_binding` остаётся pool-local attachment и runtime identity:
- explicit `pool_workflow_binding_id`;
- selector/effective scope;
- status и audit/concurrency metadata;
- pinned `binding_profile_revision_id`.

Таким образом, workflow-level reuse дополняет profile model, но не заменяет её. Preview/create-run/retry, lineage и idempotency продолжают опираться на attachment boundary вместе с pinned reusable revision.

### 2. `pool_workflow_binding` становится attachment-ом

`pool_workflow_binding` сохраняется как external/runtime identity, чтобы не ломать текущий public API и lineage path.

Но по смыслу он становится attachment-ом, который хранит только pool-specific свойства:
- `pool_id`;
- `binding_id`;
- `status`;
- `effective_from/effective_to`;
- selector scope (`direction`, `mode`, `tags`);
- ссылку на `binding_profile_id` и pinned `binding_profile_revision_id`;
- audit/concurrency fields (`revision`, `created_by`, `updated_by`, timestamps).

Reusable поля (`workflow`, `decisions`, `parameters`, `role_mapping`) больше не должны быть primary mutable payload attachment-а.

### 3. MVP без attachment-local overrides

Для первой версии attachment НЕ может переопределять:
- workflow revision;
- slot map / decision refs;
- parameters;
- role mapping.

Если конкретному пулу нужна вариация reusable схемы, корректный путь:
- выпустить новую `binding_profile_revision`; или
- создать отдельный `binding_profile`.

Это intentionally boring решение:
- убирает merge precedence rules;
- не требует diff/overlay between profile and attachment;
- делает lineage и rollback проще.

Local override / detach-from-profile может быть отдельным future change, если появится реальная потребность.

### 4. Lifecycle semantics для deactivate

`deactivate` относится к reusable profile lifecycle, а не к already persisted runtime lineage.

В MVP:
- deactivated `binding_profile` или его active catalog state НЕ МОЖЕТ использоваться для новых attach/re-attach;
- deactivated profile НЕ МОЖЕТ получать новые revisions;
- уже существующие attachment-ы, pinned на существующие `binding_profile_revision_id`, продолжают preview/create-run/retry на default path, если сам attachment active и попадает в effective scope;
- UI/operator read-model должны явно показывать, что attachment pinned на deactivated profile и требует осознанной миграции;
- emergency hard stop для already attached revisions intentionally не вводится в этом change.

Если позже понадобится аварийно отключать уже pinned reusable revision, это отдельный lifecycle state (`revoked`) и отдельный change, потому что он ломает принцип reproducible pinned runtime.

### 5. Runtime boundary остаётся attachment-based

`preview/create-run/retry` продолжают принимать explicit `pool_workflow_binding_id`.

Runtime flow:
1. резолвит attachment по `pool_workflow_binding_id`;
2. валидирует его pool-local effective scope;
3. загружает pinned `binding_profile_revision_id`;
4. строит effective runtime bundle из attachment metadata + profile revision content;
5. сохраняет lineage snapshot attachment-а и profile revision на момент запуска.

Это сохраняет текущий fail-closed контракт и не превращает profile catalog в hidden runtime selector.

### 6. Run idempotency должен учитывать и attachment, и reusable revision

`pool_workflow_binding_id` остаётся частью public contract, но profile model добавляет ещё два materially значимых параметра логики:
- `attachment revision`;
- `binding_profile_revision_id`.

Итоговая формула run fingerprint должна учитывать:
- `pool_id`;
- `period_start/effective period inputs`;
- `direction`;
- `pool_workflow_binding_id`;
- `attachment revision`;
- `binding_profile_revision_id`;
- `canonicalized(run_input)`.

Это гарантирует, что:
- pool-local изменение attachment scope/selector/repin создаёт новый fingerprint;
- repin того же attachment на новую reusable revision не reuse'ит старый run;
- lineage и idempotency остаются согласованными.

### 7. UI surfaces разделяются по ответственности

Primary authoring surface для reusable схем:
- dedicated binding profile catalog на отдельном route `/pools/binding-profiles`.

Primary operator surface для pool-local activation:
- `/pools/catalog` binding workspace.

Binding workspace в `/pools/catalog` должен:
- показывать attachment-ы;
- позволять attach existing profile revision;
- редактировать только pool-local scope (`status`, selector, effective period);
- показывать topology slot coverage относительно resolved profile revision;
- давать explicit handoff в profile catalog для правки reusable логики.

Profile catalog должен:
- list/detail/create/revise/deactivate profiles;
- показывать, какие pools используют конкретную profile revision;
- давать controlled upgrade path на новую revision.

### 8. Migration/backfill должен быть безопасным и минимальным

Для existing `pool_workflow_binding` migration path должен быть conservative:
- каждый существующий binding materialize'ится в generated `binding_profile` + `binding_profile_revision`;
- каждый существующий pool binding становится attachment-ом к resulting generated profile revision;
- migration НЕ пытается автоматически deduplicate “похожие” bindings между пулами.

Причина: semantic equality bindings слишком рискованно определять автоматически. Safe migration важнее, чем immediate consolidation.

Manual consolidation reusable схем возможна после rollout через profile catalog.

## Последствия для контрактов

### Attachment read/save contract

Attachment contract должен включать:
- `binding_id`;
- `pool_id`;
- `status`;
- `effective_from/effective_to`;
- selector fields;
- `binding_profile_id`;
- `binding_profile_revision_id`;
- read-only `binding_profile_revision_number`;
- `revision`;
- optional resolved profile summary/read-only provenance.

Attachment mutating path не должен требовать повторной отправки full reusable slot map.

### Profile read/save contract

Profile revision contract должен включать:
- stable profile identity;
- opaque `binding_profile_revision_id`;
- revision metadata;
- workflow pin;
- slot refs;
- parameters;
- role mapping;
- lifecycle/provenance fields.

## Риски и trade-offs

- Новая сущность увеличивает количество экранов и API contracts.
  - Митигируется тем, что attachment и profile разделяют responsibility и не требуют override logic в MVP.

- Если аналитики часто хотят “почти такой же профиль, но только для одного пула”, отсутствие local overrides может показаться слишком жёстким.
  - Это сознательный trade-off ради детерминированности. Если кейс станет массовым, нужен отдельный change на controlled overrides/detach.

- Active change `refactor-topology-document-policy-slots` ещё не архивирован.
  - Поэтому proposal нужно считать зависимым от slot-oriented binding model; archive/rebase потребуется перед implementation.

## План миграции

1. Зафиксировать slot-oriented binding model как prerequisite.
2. Зафиксировать `binding_profile_revision_id`, deactivate semantics и новую idempotency formula в contracts/specs.
3. Ввести profile catalog и attachment references в contracts/specs.
4. Реализовать backend models/store/read-model для profile revisions и attachments.
5. Выполнить conservative backfill existing bindings -> generated profiles.
6. Перевести `/pools/catalog` на attachment management.
7. Добавить dedicated profile catalog UI на `/pools/binding-profiles`.
8. Обновить preview/run/read-model lineage на attachment + profile provenance.
