# Change: Воспроизводимый baseline и topology UI validation runtime

## Why
Frontend UI gate сейчас зелёный, но performance evidence остаётся плохо управляемым и частично монолитным.

По состоянию на 2026-04-20 локальный full UI contour показал два системных сигнала:
- `cd frontend && npm run test:run` прошёл, но занял `738.50s total` и `470.22s tests`, тогда как последний стабильный baseline для того же gate в repo context был `337.31s total` и `218.49s tests`;
- `cd frontend && npm run test:browser:ui-platform` прошёл как один монолитный Playwright file `tests/browser/ui-platform-contract.spec.ts` на `6414` строк и `100` test cases, заняв `461.49s real` (`7.7m`) при `--workers=1`.

Проблема не только в абсолютном времени. Репозиторий пока не задаёт authoritative способ, как:
- отличать реальный runtime regression от случайного CPU/contention noise;
- сравнивать Vitest и Playwright surfaces по воспроизводимому baseline;
- review-ить и эволюционировать browser-level UI contract surface без single-file monolith.

В результате follow-up оптимизации остаются ad hoc: один шумный full run можно ошибочно принять за regression, а browser contract gate трудно профилировать и трудно локально итерировать без полного много-минутного прогона.

Нужен отдельный change, который сохранит blocking semantics полного UI gate, но введёт воспроизводимый runtime baseline workflow и explicit topology для browser contract suite.

## What Changes
- Ввести repo-owned UI validation baseline workflow с повторяемыми измерениями для полного Vitest и browser UI gate, включая явное разделение wall-clock и component breakdown.
- Зафиксировать checked-in policy, что performance improvement/regression по UI validation не оценивается по одному шумному full run без повторной выборки или объяснимого инфраструктурного фактора.
- Декомпозировать `frontend/tests/browser/ui-platform-contract.spec.ts` в explicit inventory-backed shard set по route/contract families с общими helper surfaces и без duplicate/drop coverage.
- Добавить canonical scripts для полного browser gate, focused browser reruns и runtime measurement, согласованные с `validate:ui-platform`.
- Обновить agent-facing docs и guard checks, чтобы новая topology и baseline protocol были источником истины для локальной итерации и acceptance evidence.

## Impact
- Affected specs:
  - `ui-frontend-validation-runtime` (new)
- Affected code:
  - `frontend/package.json`
  - `frontend/playwright.config.ts`
  - `frontend/tests/browser/ui-platform-contract*.spec.ts`
  - `frontend/tests/browser/**` shared helpers if shard extraction needs consolidation
  - `frontend/src/__tests__/uiPlatformBuildPath.test.ts`
  - possible new runtime governance checks under `frontend/src/__tests__/**`
  - `docs/agent/VERIFY.md`
  - `frontend/AGENTS.md`
  - optional evidence artifacts under `docs/observability/artifacts/**`

## Non-Goals
- Ослаблять blocking semantics `validate:ui-platform` или выносить browser gate из full UI acceptance contour.
- Менять product/runtime поведение UI только ради ускорения tests.
- Делать массовый rewrite всех browser contract assertions в unit tests.
- Требовать абсолютный фиксированный time budget, который не учитывает variance локального контура.

## Assumptions
- Основной structural gap сейчас находится не в отсутствии ещё одного lightweight mock, а в отсутствии воспроизводимого measurement protocol и в монолитном browser contract surface.
- Browser contract можно разрезать по route/contract families без потери invariants, если shard inventory будет checked-in и reviewable.
- Для claims о runtime improvement нужен как минимум bounded repeated measurement, иначе change рискует путать infrastructure noise с реальным regression/perf win.
