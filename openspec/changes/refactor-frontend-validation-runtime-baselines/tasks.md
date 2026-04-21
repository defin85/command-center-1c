## 1. Baseline and scope
- [x] 1.1 Зафиксировать текущий UI validation baseline для `npm run test:run` и `npm run test:browser:ui-platform`, включая variance и hottest suites/files.
- [x] 1.2 Определить canonical measurement protocol и целевые evidence artifacts/scripts для repeated runtime capture.

## 2. Browser contract topology
- [x] 2.1 Определить explicit shard boundaries для `tests/browser/ui-platform-contract.spec.ts` по route/contract families.
- [x] 2.2 Вынести monolithic browser contract в несколько checked-in shard files с общим helper surface и без duplicate/drop coverage.
- [x] 2.3 Обновить `frontend/package.json` и при необходимости `playwright.config.ts`, чтобы full browser gate и focused browser commands использовали canonical shard topology.
- [x] 2.4 Добавить или обновить guard checks, которые фиксируют canonical browser/full build path contract и не дают topology drift пройти незамеченным.

## 3. Measurement and docs
- [x] 3.1 Добавить repo-owned runtime measurement path для полного UI validation contour или его составных частей.
- [x] 3.2 Обновить `docs/agent/VERIFY.md` и `frontend/AGENTS.md`, описав repeated baseline protocol, focused browser commands и момент перехода к полному gate.
- [x] 3.3 При необходимости зафиксировать evidence artifact path для runtime comparisons, чтобы последующие perf claims ссылались на единый checked-in surface.

## 4. Validation
- [x] 4.1 Прогнать targeted verification по новым browser shard files и shared helper surfaces.
- [x] 4.2 Прогнать canonical `cd frontend && npm run test:browser:ui-platform` и подтвердить, что browser inventory не потерян и не дублируется.
- [x] 4.3 Прогнать repeated baseline measurement для `cd frontend && npm run test:run` и `cd frontend && npm run test:browser:ui-platform`, зафиксировав summary для acceptance evidence.
- [x] 4.4 Прогнать `openspec validate refactor-frontend-validation-runtime-baselines --strict --no-interactive`.
