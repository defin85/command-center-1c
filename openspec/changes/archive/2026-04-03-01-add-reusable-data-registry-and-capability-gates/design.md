## Context
Сейчас reusable-data seams распределены по независимым hardcoded спискам:
- backend enum-ы canonical entity types;
- token parser;
- bootstrap import scope;
- sync/outbox routing;
- frontend token picker и master-data forms;
- OpenAPI schemas.

Такая схема не позволяет безопасно добавлять новые reusable entity types. Система трактует появление `entity_type` в enum как implicit runtime support, хотя фактически поддержка может быть только частичной или вообще запрещённой.

## Goals / Non-Goals

### Goals
- Сделать reusable-data registry единственным executable source-of-truth.
- Перевести runtime routing и capability checks на fail-closed модель.
- Опубликовать generated registry contract для frontend и `contracts/**`.
- Подготовить foundation для additive onboarding `GLAccount` и будущих reusable entity types.

### Non-Goals
- Не поставлять в этом change новые operator-facing entity types.
- Не менять factual runtime contracts.
- Не вводить новый top-level service или новый отдельный UI app.

## Decisions

### Decision: Registry authoring живёт только в backend
Определение reusable entity types, их capability matrix и routing policy должно редактироваться только в backend source-of-truth. Frontend и contracts pipeline получают generated artifact, а не собственную параллельную конфигурацию.

### Decision: Capability matrix default-deny
Любой reusable-data action считается неподдержанным, пока registry явно не разрешит его для конкретного entity type и runtime seam. Это касается как mutating sync directions, так и bootstrap/token exposure.

### Decision: Registry управляет не только metadata, но и execution seams
Registry должен определять не только display catalog, но и реальные runtime decisions:
- может ли тип участвовать в bootstrap;
- может ли тип попадать в outbox;
- может ли тип иметь token exposure;
- может ли тип попадать в sync/readiness routing.

### Decision: Runtime endpoint не является primary contract
Диагностический endpoint с registry read-model допустим, но primary contract для frontend и generated clients должен формироваться compile-time через generated schema/artifact.

### Decision: Existing enum/switch paths остаются только как compatibility wrappers
На переходный период допустимы адаптеры поверх существующих enum/switch веток, но они должны читать одно решение из registry и не создавать второй source-of-truth.

## Rollout
1. Ввести backend registry и generated artifact без расширения shipped entity catalog.
2. Перевести token parser, bootstrap catalogs и sync/outbox gating на registry checks.
3. Оставить compatibility wrappers для существующих entity types.
4. Только после этого добавлять reusable account family в следующих changes.

## Risks / Trade-offs
- Foundation change сам по себе почти не добавляет operator-visible features.
  - Это нормально: он снимает системный риск перед account rollout.
- Появится временный слой совместимости между registry и legacy enum paths.
  - Это сознательный мост; долг должен закрываться следующими changes, а не игнорироваться.
