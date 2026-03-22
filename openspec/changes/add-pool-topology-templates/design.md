## Context

Сейчас reusable слой в domain уже появился для workflow/binding logic через `binding_profile_revision`, но topology остаётся concrete и pool-local. В результате повторяющиеся схемы приходится:
- либо собирать руками заново в каждом `pool`,
- либо копировать целый `pool`, а затем переназначать организации и edge metadata.

Оба пути слабо выражают доменную идею “одна и та же схема распределения используется многократно разными пулами”.

При этом existing runtime/document-policy model уже завязан на explicit `edge.metadata.document_policy_key`, а не на raw policy payload в topology. Значит reuse topology должен строиться вокруг:
- reusable abstract graph;
- pool-local assignment concrete организаций в abstract slots;
- explicit default selectors на edges;
- materialized concrete graph для текущего runtime.

## Goals / Non-Goals

- Goals:
  - отделить reusable shape graph от concrete организаций;
  - дать штатный path тиражирования topology между пулами;
  - сохранить explicit `document_policy_key` как canonical runtime selector;
  - не вводить “магическое” поведение, вычисляемое только по degree/position узла;
  - сохранить текущий concrete graph/runtime layer как execution model;
  - выполнить rollout без in-place migration existing pool graph и связанных binding данных.

- Non-Goals:
  - не превращать pool clone в основной механизм reuse;
  - не делать cross-tenant template library;
  - не заменять все existing topology APIs новым read model в одном change;
  - не вводить full graph inference engine, который сам решает `multi/receipt/realization` без explicit preset;
  - не убирать manual topology authoring;
  - не конвертировать автоматически существующие `pool` в templates; затронутые `pool` допускается удалить и пересоздать.

## Decisions

### 1. Reusable topology хранится как template/revision, а не как “абстрактные организации”

Новая reusable модель должна описывать:
- template identity (`code`, `name`, `status`);
- versioned revision;
- abstract nodes со стабильными `slot_key`;
- abstract edges между slot-ами;
- optional default `document_policy_key` на template edge.

Template revision не хранит concrete `organization_id`, `inn` или другие признаки конкретной организации.

Rationale:
- reusable единицей является graph shape и role layout, а не псевдо-организация;
- иначе модель смешает legal/business entity и topology role.

### 2. Pool pin-ит конкретную template revision и задаёт slot assignments

Pool-local instantiation должна сохранять:
- `pool_id`;
- `topology_template_revision_id`;
- mapping `slot_key -> organization_id`;
- optional pool-local metadata, не меняющую сам shape graph.

Instantiation пинится на конкретную revision. Появление новой template revision не должно ретроактивно менять уже созданные пулы.

Rationale:
- reuse остаётся детерминированным и audit-friendly;
- migration на новую revision становится явным действием, а не скрытым drift.

### 3. Existing concrete pool graph остаётся runtime/materialized representation

Current `PoolNodeVersion` / `PoolEdgeVersion` and graph endpoints already обслуживают validation, preview и execution runtime. Этот change не должен ломать существующий shipped execution model.

Поэтому template instantiation materialize'ит concrete graph в текущий runtime layer, а existing graph API остаётся operator/runtime-facing read path.

В MVP template path применяется к новым или явно пересозданным после hard reset пулам. Change не требует in-place conversion already existing concrete graph.

Rationale:
- это минимальный путь без большого runtime refactor;
- change добавляет reusable authoring layer, а не переписывает весь execution stack.

### 4. Edge behavior defaults задаются template edge preset, а не graph-shape inference

Для template edge допускается хранить default `document_policy_key`, например:
- `realization`
- `multi`
- `receipt`

При instantiation этот default materialize'ится в concrete `edge.metadata.document_policy_key`, если оператор явно не переопределил его.

Runtime и preview продолжают резолвить policy только из explicit concrete edge selector. Система не должна “догадываться”, что leaf в top-down значит `receipt`, если explicit selector отсутствует.

Rationale:
- один и тот же graph shape не всегда однозначно задаёт бизнес-смысл edge;
- explicit preset оставляет reuse удобным, но не размывает source-of-truth.

### 5. Manual topology authoring остаётся fallback path

Для нестандартных или разовых схем `/pools/catalog` может по-прежнему позволять manual snapshot authoring. Но canonical reuse path для типовых новых пулов должен идти через template instantiation.

Rationale:
- это снижает риск блокировки оператора на corner cases;
- при этом типовые сценарии перестают зависеть от ручной сборки графа.

### 6. Rollout выполняется без automatic conversion existing pools

Change не включает automatic extraction existing manual pool graphs в `topology_template_revision` и не требует преобразования уже настроенных `pool` in place.

Вместо этого rollout допускает destructive reset затронутых `pool` и связанных reusable binding данных с последующим пересозданием через template-based path.

Rationale:
- это минимизирует implementation scope и убирает сложный migration layer;
- текущие данные не являются ценным долгосрочным legacy contract для этого refactor.

## Alternatives Considered

### 1. Оставить только pool clone

Rejected:
- clone копирует concrete state, но не формализует reusable intent;
- drift между пулами становится нормой;
- provenance “какая общая схема лежит под этим pool” быстро теряется.

### 2. Шаблонизировать только edge behavior

Rejected:
- reusable edge presets без reusable graph shape не решают главную проблему тиражирования topology;
- оператор всё равно будет каждый раз вручную строить узлы и связи;
- одно лишь положение узла в графе не всегда достаточно для однозначного выбора behavior.

### 3. Вычислять `document_policy_key` только по graph shape

Rejected:
- даёт неявное и трудно аудируемое поведение;
- разветвлённые графы быстро создадут неоднозначные случаи;
- противоречит existing explicit-slot contract вокруг `edge.metadata.document_policy_key`.

### 4. Автоматически конвертировать existing pools в topology templates

Rejected:
- добавляет дорогой migration layer ради данных, которые можно пересоздать;
- усложняет rollout и повышает риск несовместимой materialization;
- не нужен для достижения reusable template model в MVP.

## Risks / Trade-offs

- Появляется ещё один доменный слой поверх current concrete topology.
  - Mitigation: оставить concrete graph runtime model без немедленного refactor.

- Materialization из template revision в concrete graph создаёт rollout/consistency точку.
  - Mitigation: pin на revision, explicit apply/update flow, optimistic concurrency, deterministic materialization и destructive reset старых данных вместо conversion path.

- Слишком свободные pool-local overrides могут размыть пользу templates.
  - Mitigation: в MVP ограничить pool-local instantiation mapping'ом slot-ов и явным edge selector override только там, где это действительно нужно.

- Manual topology editor и template path могут конфликтовать как два равноправных authoring mode.
  - Mitigation: зафиксировать template instantiation как preferred reuse path, manual editor как fallback/remediation.

## Rollout Plan

1. Добавить новую reusable capability `pool-topology-templates`.
2. Определить contract template revision: abstract nodes, abstract edges, default edge selectors.
3. Определить pool instantiation contract: pin на revision + slot assignments.
4. До включения нового authoring path удалить затронутые `pool` и связанные reusable binding данные вместо in-place conversion existing graphs.
5. Зафиксировать, что instantiation materialize'ит current concrete graph/runtime layer только для новых или пересозданных pool.
6. Расширить `/pools/catalog` template-based authoring path без удаления manual editor.
7. Сохранить existing runtime resolution document policy через explicit concrete `edge.metadata.document_policy_key`.
