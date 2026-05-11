## 1. Baseline and scope
- [x] 1.1 Зафиксировать heavy frontend test perimeter и repo-owned scripts, которые сегодня создают основной runtime/CPU contention.
- [x] 1.2 Подтвердить canonical target files/scripts/docs для change execution matrix.

## 2. Test runner topology
- [x] 2.1 Обновить `frontend/vitest.config.ts`, введя canonical partitioning между fast/default tests и heavy route suites.
- [x] 2.2 Для каждого runtime perimeter завести explicit project name, shared inheritance path и mutually exclusive file selection.
- [x] 2.3 Для heavy route perimeter убрать вредный over-parallelization и зафиксировать bounded execution order/worker policy.
- [x] 2.4 В первой итерации сохранить текущие `pool` / `isolate` semantics; выносить их в follow-up только при недостаточности topology fix.
- [x] 2.5 При необходимости укрепить общий test harness/cleanup для heavy suites, если без этого topology остаётся flaky.
- [x] 2.6 Профилировать residual worst-file tails и зафиксировать bounded split boundary для `PoolRunsPage.test.tsx` и `PoolMasterDataPage.test.tsx`.
- [x] 2.7 Физически split `frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx` на scenario-focused files с общим helper surface и без duplicate inventory.
- [x] 2.8 Физически split `frontend/src/pages/Pools/__tests__/PoolMasterDataPage.test.tsx` на scenario-focused files с общим helper surface и без duplicate inventory.

## 3. Repo-owned commands and docs
- [x] 3.1 Обновить `frontend/package.json`, чтобы focused commands и full gate использовали новую topology без скрытых расхождений.
- [x] 3.2 Обновить `docs/agent/VERIFY.md` и `frontend/AGENTS.md`, описав fast path, heavy path и full gate.
- [x] 3.3 Добавить/обновить guard checks, если в репозитории уже есть тесты, которые фиксируют validation/build path contract.

## 4. Validation
- [x] 4.1 Прогнать минимальный релевантный verification set на focused heavy surfaces.
- [x] 4.2 Прогнать focused verification set на новых split suite files и shared helper surfaces.
- [x] 4.3 Прогнать `cd frontend && npm run test:run` и подтвердить, что inventory не потерян, а canonical full gate завершает change без ручного прерывания.
- [x] 4.4 Подтвердить, что heavy suites не исполняются повторно одновременно через fast и heavy perimeter после обновлённого inventory.
- [x] 4.5 Прогнать `openspec validate refactor-frontend-test-runtime-governance --strict --no-interactive`.
