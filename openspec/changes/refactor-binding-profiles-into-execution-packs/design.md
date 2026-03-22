## Context

Сейчас `Binding Profiles` выступают reusable catalog для workflow/slot logic и attach'ятся к конкретным пулам через `pool_workflow_binding`. Это уже ближе к reusable execution layer, чем к topology layer.

После `add-pool-topology-templates` structural slot-ы и shape graph получают отдельного владельца:
- topology template revision описывает abstract nodes/edges;
- template revision определяет structural slot namespace;
- concrete pool materialize'ит graph из template + slot assignments.

В этой картине текущий термин `Binding Profiles` становится неудачным:
- он звучит как structural binding к topology;
- он скрывает фактическую роль reusable execution pack;
- он размывает границу между slot namespace и slot implementation.

Так как затронутые `binding_profile*`, attachment и связанные `pool` данные допускается удалить до rollout, change не обязан тащить staged compatibility migration ради сохранения текущего каталога.

## Goals / Non-Goals

- Goals:
  - ввести понятный доменный/операторский термин `Execution Pack`;
  - отделить structural slot ownership от executable slot implementation ownership;
  - сохранить immutable revision pin и reproducible runtime;
  - выполнить reframe как clean rename без migration/backfill existing data и без обязательного compatibility alias layer;
  - подготовить более ясную модель для future topology-template integration.

- Non-Goals:
  - не сохранять existing `binding_profile*`, attachment и затронутые `pool` данные ценой отдельного migration/alias layer;
  - не сливать execution pack и topology template в одну сущность;
  - не менять explicit attachment/runtime identity;
  - не переносить workflow/parameters/role mapping в topology template;
  - не вводить silent fallback на legacy naming.

## Decisions

### 1. `Execution Pack` становится новой operator-facing и доменной моделью reusable execution logic

Execution pack revision хранит:
- pinned workflow revision;
- decision refs, реализующие named slot implementations;
- default parameters;
- role mapping;
- revision metadata/provenance.

Execution pack не хранит:
- concrete topology shape;
- abstract graph nodes/edges;
- ownership structural slot namespace.

Rationale:
- это честно отражает фактическую ответственность reusable behavior layer;
- термин перестаёт конфликтовать с topology template semantics.

### 2. Structural slot namespace принадлежит topology template, execution pack только реализует slot keys

После topology-template rollout slot keys должны трактоваться как structural contract, приходящий из selected topology template revision или materialized concrete topology, а не как namespace, придумываемый execution pack catalog.

Execution pack revision использует `slot_key` только как ключ реализации:
- “для slot `sale` исполняется вот эта decision revision”;
- “для slot `receipt` исполняется вот этот policy pack”.

Rationale:
- один и тот же execution pack может быть совместим с несколькими topology templates, если их slot namespace пересекается;
- topology shape и executable implementation не сливаются в один catalog.

### 3. Rollout выполняется как clean rename без compatibility alias layer

Shipped contract этого change использует `Execution Pack` как primary operator-facing и API semantics без обязательного compatibility alias path для existing `binding_profile*` data.

При этом immutable opaque revision id остаётся runtime pin. Его роль не меняется, даже если старые данные удаляются и catalog переезжает на execution-pack naming.

Rationale:
- hard reset данных дешевле и чище, чем поддержка временного двуязычного контракта;
- доменная модель сразу становится однозначной без transition tax.

### 4. Pool attachment остаётся activation layer, pinned на execution-pack revision

`pool_workflow_binding` не становится execution logic owner. Он остаётся pool-local activation layer, pinned на immutable revision reusable execution pack.

Operator-facing read model attachment-а должен описывать:
- какой execution pack attached;
- какая execution-pack revision pinned;
- какую coverage/compatibility она имеет относительно topology template slots.

Rationale:
- это сохраняет separation of concerns;
- упрощает reasoning про “shape vs behavior vs activation”.

## Alternatives Considered

### 1. Полностью удалить `Binding Profiles` и встроить execution logic в topology templates

Rejected:
- topology template станет перегруженной сущностью;
- один reusable graph shape перестанет переиспользоваться с разными execution variants;
- workflow/decision/parameters/role-mapping начнут жить там, где им не место.

### 2. Оставить текущий термин `Binding Profiles`

Rejected:
- после topology templates термин начнёт системно путать shape/slot ownership и execution logic;
- operator-facing mental model останется неясной;
- часть будущего API/UI hardening будет строиться вокруг уже слабого названия.

### 3. Сохранить staged migration и compatibility aliases

Rejected:
- prolongs старый mental model и переходный код;
- создаёт лишний rollout scope ради данных, которые допускается удалить;
- мешает быстро зафиксировать clean ownership split между topology template и execution pack.

## Risks / Trade-offs

- Clean rename затрагивает больше operator-facing copy, API и тестов в одном шаге.
  - Mitigation: scope ограничивается reusable execution catalog и attachment semantics, а затронутые данные удаляются до rollout.

- Если `add-pool-topology-templates` задержится, часть semantics execution-pack model останется “подвешенной”.
  - Mitigation: явно указать dependency и sequencing в change/tasks.

- UI rename маршрута и терминов затронет много тестов и handoff links.
  - Mitigation: единый primary route/copy без alias layers и явный hard-reset rollout checklist.

## Rollout Plan

1. Зафиксировать в specs, что reusable execution logic теперь описывается как `Execution Pack`.
2. Зафиксировать ownership split:
   - topology templates own structural slots;
   - execution packs own executable implementations.
3. До включения нового контракта удалить affected `binding_profile*`, attachment и при необходимости `pool` данные вместо migration legacy catalog.
4. Обновить operator-facing catalog surface и handoff semantics на `Execution Packs` без обязательного legacy alias route.
5. Сохранить immutable revision pin и reproducible runtime lineage под новым execution-pack semantics.
