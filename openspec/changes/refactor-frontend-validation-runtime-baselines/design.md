## Context
- Предыдущий change `refactor-frontend-test-runtime-governance` уже partitioned Vitest heavy route suites и снизил worst-case cost full frontend gate.
- Несмотря на это, локальный full UI contour 2026-04-20 остался шумным:
  - `npm run test:run`: `738.50s total`, `470.22s tests`, `359.39s import`, hottest files в основном из heavy Pools families;
  - последний стабильный baseline в repo context: `337.31s total`, `218.49s tests`;
  - `npm run test:browser:ui-platform`: `100 passed`, `461.49s real`, при этом весь browser contract живёт в одном файле `tests/browser/ui-platform-contract.spec.ts`.
- Текущий browser gate уже является authoritative coverage surface для non-lintable UI invariants, но его runtime topology и perf evidence governance почти не формализованы.

## Goals / Non-Goals
- Goals:
  - Сделать UI validation runtime измеряемым и воспроизводимым, а не зависящим от одного случайного full run.
  - Разбить browser contract monolith на reviewable shard set с общим helper surface и explicit ownership.
  - Сохранить full UI gate blocking и canonical, но дать bounded focused browser reruns для локальной итерации.
  - Зафиксировать в docs и guard tests, как repo считает perf evidence для UI validation.
- Non-Goals:
  - Полностью переписать browser contract на другой test framework.
  - Гарантировать один жёсткий wall-clock SLA для любого developer machine.
  - Ослаблять сами browser invariants ради более быстрого прогона.

## Decisions

### Decision 1: Performance claims по UI validation должны опираться на repo-owned repeated baseline workflow
Любой change, который заявляет improvement/regression UI validation runtime, должен использовать checked-in measurement path и bounded repeated samples вместо одного произвольного full run.

Почему:
- current contour уже показал variance почти в `2x` для `test:run`;
- один noisy run не позволяет отделить инфраструктурную перегрузку от реального regression;
- repeated samples и явный breakdown (`tests`, `import`, `environment`, browser wall-clock) делают perf claims reviewable.

Expected shape:
- repo-owned command(s) для measurement;
- минимум несколько последовательных samples или equivalent scripted median/min/max summary;
- отдельная фиксация Vitest и Playwright numbers.

### Decision 2: Browser UI contract должен стать inventory-backed shard topology, а не single-file monolith
`tests/browser/ui-platform-contract.spec.ts` должен быть decomposed в несколько checked-in files по route/contract families, использующих общие helpers.

Почему:
- single-file monolith плохо review-ить и тяжело локально rerun-ить точечно;
- file-level topology нужна, если проект захочет profiling-backed worker policy, а не только линейный `--workers=1`;
- shard inventory делает coverage explicit и позволяет защититься от silent drop/duplicate execution.

Boundaries:
- split идёт по осмысленным contract families (`workspace restore/mobile detail`, `runtime handoff`, `runtime control`, `locale/a11y`, и т.п.), а не по arbitrary line-count;
- общий helper слой остаётся checked-in reusable surface;
- canonical full browser gate собирает все shards через repo-owned script.

### Decision 3: Blocking full UI gate остаётся source of truth
`validate:ui-platform` и canonical browser gate остаются обязательными acceptance commands. Focused browser commands и measurement scripts ускоряют iteration и evidence capture, но не заменяют full gate.

### Decision 4: Browser runtime policy меняется только вместе с измерением и explicit topology
Если после shard split проект захочет менять `--workers` или иные Playwright execution knobs, это должно происходить на основе repeated measurement и checked-in script/config surface, а не через разовые CLI override в handoff.

Почему:
- иначе runtime semantics опять станут ad hoc;
- full gate должен оставаться воспроизводимым между локальной итерацией и acceptance run.

## Alternatives Considered

### A1. Оставить browser contract в одном файле и просто чаще запускать его вручную
Отклонено: не решает reviewability, focused iteration и explicit ownership problem.

### A2. Считать один full run достаточным perf evidence
Отклонено: текущий contour уже показал, что один run может быть сильно noisy и приводить к ложным выводам.

### A3. Ускорять только Vitest surface, не трогая Playwright topology
Отклонено: после предыдущего change вторым системным tail стал именно browser contract monolith.

## Risks / Trade-offs
- Shard split browser suite добавит больше файлов и потребует discipline в поддержке общего helper слоя.
- Repeated measurement удлинит acceptance workflow для perf-centric changes.
- Слишком агрессивная shard parallelism policy может поднять flakiness, если shared state boundaries окажутся неочевидными.

## Validation Strategy
- Прогнать новые focused browser shards напрямую и убедиться, что они покрывают ожидаемые route/contract families.
- Прогнать canonical `npm run test:browser:ui-platform` после split и подтвердить отсутствие duplicate/drop coverage.
- Зафиксировать repeated baseline evidence для `npm run test:run` и `npm run test:browser:ui-platform`.
- Прогнать `openspec validate refactor-frontend-validation-runtime-baselines --strict --no-interactive`.
