## Context
- `frontend/test:run` сейчас равен простому `vitest run`.
- `validate:ui-platform` опирается на полный `test:run`, поэтому каждый frontend build gate платит стоимость самых тяжёлых route suites.
- В кодовой базе уже есть явный маркер тяжёлых suite: `HEAVY_ROUTE_TEST_TIMEOUT_MS=120000`.
- Hot spots по текущему inventory включают как минимум:
  - `PoolRunsPage.test.tsx`
  - `PoolMasterDataPage.test.tsx`
  - `PoolCatalogPage.{core,bindings,topology,errors-sync}.test.tsx`
  - `PoolBindingProfilesPage.test.tsx`
  - `DecisionsPage.test.tsx`
- После topology split, cache-path и targeted suite hardening основной residual tail остался в двух монолитных Pools files:
  - `PoolRunsPage.test.tsx` как stage-heavy route flow file
  - `PoolMasterDataPage.test.tsx` как multi-zone/bootstrap/sync route flow file
- Это означает, что дальше bottleneck находится не столько в global worker policy, сколько в worst-file wall-clock и длинных scenario chains внутри отдельных test modules.

## Goals / Non-Goals
- Goals:
  - Снизить CPU contention и wall-clock cost full frontend test runtime без потери coverage.
  - Дать repo-owned short path для локальной итерации по тяжёлым route families.
  - Сохранить `validate:ui-platform` как blocking gate, но сделать его topology-aware.
  - Довести canonical `cd frontend && npm run test:run` до подтверждённо проходящего состояния внутри этого change, а не оставлять full gate как открытый residual risk.
- Non-Goals:
  - Полный rewrite больших route suites.
  - Внедрение внешнего test orchestrator вместо Vitest.
  - Переопределение browser gate semantics.

## Decisions

### Decision 1: Использовать Vitest projects как canonical topology
Full frontend test runtime будет partitioned через `test.projects`, а не через набор ad hoc shell scripts.

Почему:
- topology остаётся частью checked-in runner config;
- `vitest run` и repo-owned scripts используют один источник истины;
- heavy project может получить собственные `fileParallelism` / `groupOrder` ограничения без глобального `maxWorkers=1` для всего репозитория.
- Для сохранения текущего shared runner behavior каждый inline project ДОЛЖЕН использовать explicit `name` и явное наследование shared root config (`extends: true` или эквивалентный merge path), потому что root `vitest.config` сам по себе не исполняется как project surface.

### Decision 2: Heavy route suites должны быть explicit inventory-backed surface
Heavy suites будут перечислены или покрыты bounded glob-patterns в конфиге, а не определяться скрыто по line-count или эвристикам runtime.

Почему:
- surface должен быть reviewable;
- docs, scripts и runtime config могут ссылаться на один и тот же explicit perimeter;
- drift проще ловить при ревью и тестах.
- Каждый test file должен принадлежать ровно одному runtime perimeter, чтобы topology не теряла coverage и не удваивала выполнение тяжёлых suites.

### Decision 3: Full gate сохраняет coverage, short path ускоряет итерацию
`validate:ui-platform` остаётся blocking и по-прежнему включает полный frontend test surface. Ускорение достигается не ослаблением coverage, а более безопасным исполнением heavy suites и появлением canonical focused commands.

### Decision 4: В первой итерации не менять `pool` и `isolate`
Первый rollout ограничивается topology, inventory и repo-owned command surface. Переключение `pool` (`forks` -> `threads`) или ослабление isolation не входит в initial implementation, если только profiling не докажет, что partitioning недостаточно.

Почему:
- official Vitest guidance допускает `threads` и selective `isolate: false` как performance knobs, но одновременно отмечает compatibility trade-off;
- текущий frontend perimeter использует `jsdom`, React Testing Library и heavy route suites с большим количеством side effects;
- смешивание topology refactor и execution semantics усложнит root-cause analysis при regressions/flakiness.

### Decision 5: Residual monolith suites нужно декомпозировать физически, если topology уже не снимает worst-file tail
Если после explicit Vitest topology, cache-path и harness hardening canonical full gate всё ещё блокируется worst-file wall-clock, remaining monolith suites должны split'иться на меньшие scenario-focused files с общим helper surface.

В рамках этого change это относится именно к:
- `frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx`
- `frontend/src/pages/Pools/__tests__/PoolMasterDataPage.test.tsx`

Почему:
- текущий residual risk change находится именно в невозможности доказать устойчивый `npm run test:run`, а не в отсутствии ещё одного npm script;
- topology уже ограничила contention между файлами, поэтому следующий существенный выигрыш лежит внутри самих worst single-file suites;
- physical split улучшает reviewability scenario families, future project balancing и targeted reruns без смены product semantics.

Правило bounded implementation:
- split идёт по scenario families / route zones / stage flows, а не по случайному line-count;
- shared builders/mocks/helpers остаются checked-in reusable surface, чтобы не плодить copy-paste test harness;
- новый inventory должен остаться exclusive и reviewable через checked-in runtime perimeter.

## Alternatives Considered

### A1. Глобально опустить весь Vitest до `maxWorkers=1`
Отклонено: снижает CPU, но превращает любой full run в линейный долгий прогон и наказывает быстрые unit files.

### A2. Оставить `vitest run` как есть и просто добавить больше точечных npm scripts
Отклонено: помогает локально, но не исправляет full gate topology и не убирает contention/flakiness в canonical path.

### A3. Массово переписать крупные route suites в component/unit tests
Отклонено для этого change: это полезное follow-up направление, но не минимальный bounded fix для нынешнего runtime pain.

### A4. Остановиться на topology/cache и закрыть change без успешного full gate
Отклонено: change прямо затрагивает canonical frontend test runtime governance, поэтому отсутствие доказанного `npm run test:run` оставляет главный acceptance hole открытым.

## Risks / Trade-offs
- Heavy project inventory может устаревать и требовать поддержки по мере появления новых large route suites.
- При неудачном group order projects всё ещё могут конкурировать за ресурсы; это нужно валидировать целевыми прогонами.
- Часть suite может требовать дополнительного cleanup hardening, если текущая медлительность вызвана не только contention, но и долгими async tails.
- Если inventory не будет exclusive, heavy suites могут выполняться дважды: один раз в fast perimeter и ещё раз в heavy perimeter, что убьёт часть ожидаемого выигрыша.
- Physical split может разнести shared setup по нескольким файлам и создать helper drift, если не удерживать общий reusable harness.
- Если split сделать по случайным границам вместо scenario families, можно снизить runtime ценой худшей читабельности и более дорогого future maintenance.

## Validation Strategy
- Проверить focused commands для heavy surfaces (`Pools`, `Decisions`) после partitioning.
- После targeted split прогнать новые split suites напрямую и убедиться, что old monolith inventory полностью заменён без duplicate execution.
- Проверить, что `npm run test:run` видит оба project surface и не теряет test inventory.
- Сравнить runtime/CPU behavior на targeted hot spots относительно текущего baseline.
