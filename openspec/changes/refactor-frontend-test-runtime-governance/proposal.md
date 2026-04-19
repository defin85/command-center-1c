# Change: Глобальная оптимизация runtime frontend test gate

## Why
Локальный frontend verification contour стал слишком тяжёлым для ежедневной работы: `npm run test:run` и `npm run validate:ui-platform` регулярно утыкаются в многоминутные route-level suite, создают высокий CPU contention и ухудшают signal/noise для точечных правок.

Проблема уже видна в repo-owned surface:
- `validate:ui-platform` всегда запускает полный `vitest run`, browser gate и production build;
- в `frontend/src/pages/**/__tests__` накопились integration-heavy suite с `HEAVY_ROUTE_TEST_TIMEOUT_MS=120000`;
- отдельные repo-owned scripts, например `test:run:pools-catalog`, дополнительно разгоняют тяжелые route suites через `--maxWorkers 4`, что усиливает contention и flaky tails.

После первого этапа topology/cache work CPU contention уже заметно снижен, но change всё ещё не закрыт: canonical `cd frontend && npm run test:run` не подтверждён как устойчиво проходящий full gate, а остаточный wall-clock tail сосредоточился в двух монолитных suite:
- `PoolRunsPage.test.tsx`
- `PoolMasterDataPage.test.tsx`

Пока эти файлы остаются single-file hot spots, verification остаётся неполным, а full gate completion трудно доказать без ручного прерывания long-running contour.

Нужно зафиксировать отдельный change, который сохранит blocking coverage, но переведёт frontend tests на управляемую topology исполнения с bounded fast-path и low-contention heavy path.

## What Changes
- Ввести canonical test-runtime partitioning для frontend Vitest surface:
  - fast/default project для обычных unit/light integration tests;
  - dedicated heavy-route project(s) для integration-heavy route suites без агрессивной file-level parallelism.
- Перевести repo-owned frontend test scripts на эту topology, чтобы full gate оставался blocking, но не тратил CPU на вредный over-parallelization.
- Добавить repo-owned focused commands для тяжёлых route families (`Pools`, `Decisions` и т.п.), чтобы локальная итерация не требовала полного `vitest run`.
- Обновить agent-facing verification docs и guidance, чтобы canonical short path и full gate были описаны явно и согласованно.
- Добить canonical verification contour до успешного `cd frontend && npm run test:run` и зафиксировать evidence, что heavy inventory не теряется и не исполняется повторно.
- Физически split `frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx` и `frontend/src/pages/Pools/__tests__/PoolMasterDataPage.test.tsx` на меньшие scenario-focused files с общими helper surfaces, чтобы убрать worst single-file tail, который topology уже не может погасить сам по себе.

## Impact
- Affected specs:
  - `ui-frontend-test-runtime` (new)
- Affected code:
  - `frontend/vitest.config.ts`
  - `frontend/package.json`
  - `frontend/src/test/**` and targeted heavy suite helpers if runtime cleanup needs hardening
  - `frontend/src/pages/Pools/__tests__/PoolRunsPage*.test.tsx`
  - `frontend/src/pages/Pools/__tests__/PoolMasterDataPage*.test.tsx`
  - `docs/agent/VERIFY.md`
  - `frontend/AGENTS.md`
  - possible guard tests under `frontend/src/__tests__/**`

## Non-Goals
- Переписывать в этом change все большие route suites в мелкие component tests.
- Делать массовый split всех heavy route families; targeted split ограничен residual монолитами `PoolRunsPage` и `PoolMasterDataPage`.
- Ослаблять blocking semantics `validate:ui-platform` или убирать browser gate.
- Менять product/runtime поведение UI ради ускорения tests, если это не требуется для устранения test-induced contention.

## Assumptions
- Основной выигрыш даст изменение test runner topology и repo-owned commands, а не только локальная оптимизация одного конкретного suite.
- Heavy route files можно определить через checked-in test inventory и поддерживать как explicit config surface без скрытой магии.
- После topology/cache hardening главные residual tails действительно локализованы в `PoolRunsPage.test.tsx` и `PoolMasterDataPage.test.tsx`, поэтому targeted physical split этих файлов является bounded step, а не новым бесконтрольным расширением scope.
