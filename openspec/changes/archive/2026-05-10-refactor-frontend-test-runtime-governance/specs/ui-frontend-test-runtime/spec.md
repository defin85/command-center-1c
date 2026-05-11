## ADDED Requirements
### Requirement: Frontend Vitest surface MUST isolate heavy route suites from default test runtime
Система ДОЛЖНА (SHALL) исполнять integration-heavy frontend route suites через отдельный checked-in Vitest runtime perimeter, который не конкурирует с обычными unit/light integration files за тот же агрессивный file-level parallelism.

Каждый frontend test file ДОЛЖЕН (SHALL) принадлежать ровно одному runtime perimeter, чтобы topology не приводила к скрытому drop или дублированному исполнению одного и того же suite.

#### Scenario: Full frontend test run keeps heavy suites in dedicated runtime perimeter
- **GIVEN** разработчик или CI запускает canonical frontend unit/integration gate
- **WHEN** в test inventory присутствуют heavy route suites (`Pools`, `Decisions` или эквивалентные inventory-backed files)
- **THEN** эти suites исполняются через dedicated runtime perimeter с bounded worker/file parallelism
- **AND** fast/default tests не теряют coverage, но не делят тот же over-parallelized execution path с heavy files

#### Scenario: Heavy perimeter is explicit and reviewable
- **GIVEN** в репозитории появляется новый heavy route suite
- **WHEN** команда обновляет frontend test runtime topology
- **THEN** heavy perimeter выражается checked-in config/inventory surface
- **AND** его можно review-ить и документировать без скрытых runtime heuristics

#### Scenario: Topology avoids duplicate execution across perimeters
- **GIVEN** heavy route suites и fast/default suites распределены по нескольким Vitest projects
- **WHEN** запускается canonical full frontend test run
- **THEN** каждый test file исполняется ровно один раз
- **AND** heavy suite не попадает одновременно и в fast perimeter, и в dedicated heavy perimeter

### Requirement: Repo-owned frontend test commands MUST expose bounded fast-path and heavy-path workflows
Система ДОЛЖНА (SHALL) предоставлять repo-owned команды для локальной итерации, которые позволяют запускать только релевантный fast path или scoped heavy path без обязательного полного `vitest run`.

#### Scenario: Developer iterates on heavy route family without full-suite rerun
- **GIVEN** разработчик меняет `Pools` или другой heavy route family
- **WHEN** он использует repo-owned focused test command
- **THEN** запускаются только релевантные heavy files для этой family
- **AND** команда не требует полного frontend test surface для каждого шага итерации

#### Scenario: Agent-facing docs describe canonical short path
- **GIVEN** агент или разработчик читает repo-owned frontend verification docs
- **WHEN** ему нужен быстрый feedback loop
- **THEN** docs указывают canonical focused commands и момент, когда нужно переходить к full gate
- **AND** этот guidance согласован с `package.json` и test runner config

#### Scenario: Focused commands reuse canonical runtime perimeter
- **GIVEN** в репозитории определён dedicated heavy runtime perimeter
- **WHEN** repo-owned focused command запускает scoped heavy validation
- **THEN** команда использует canonical project/perimeter filtering
- **AND** не вводит bespoke parallelism override, расходящийся с checked-in runtime topology

### Requirement: Full frontend validation gate MUST preserve blocking coverage while using optimized test topology
Система ДОЛЖНА (SHALL) сохранять blocking semantics frontend validation gate даже после оптимизации runtime topology: полный gate остаётся source-of-truth, но использует checked-in partitioning вместо ad hoc over-parallelized execution.

Первая итерация этого change НЕ ДОЛЖНА (SHALL NOT) одновременно менять `pool` или global test isolation semantics, если этого не требует отдельный profiling-backed follow-up.

#### Scenario: Validation gate remains blocking after topology split
- **GIVEN** разработчик запускает canonical full frontend validation gate
- **WHEN** test runtime topology уже partitioned на fast/default и heavy perimeter
- **THEN** gate по-прежнему выполняет весь обязательный frontend test surface
- **AND** изменение не может считаться готовым при падении любой обязательной части gate

#### Scenario: Optimized topology does not silently drop heavy test inventory
- **GIVEN** heavy route suites существуют в checked-in test inventory
- **WHEN** запускается canonical full frontend test run
- **THEN** heavy suites всё ещё исполняются как часть full gate
- **AND** оптимизация topology не превращается в скрытое ослабление coverage

#### Scenario: Change is not accepted on focused evidence alone when full gate is still unresolved
- **GIVEN** focused heavy-surface checks и repo-owned short-path commands уже зелёные
- **WHEN** canonical `cd frontend && npm run test:run` всё ещё не завершён успешно
- **THEN** change не считается завершённым
- **AND** full gate completion остаётся обязательным acceptance evidence

### Requirement: Residual monolithic heavy suites MUST be decomposed when they block canonical full-gate completion
Если после topology split, cache-path и harness hardening worst-file wall-clock всё ещё блокирует canonical frontend full gate, система ДОЛЖНА (SHALL) декомпозировать residual monolith suites в меньшие scenario-focused files с общим checked-in helper surface.

Такой split НЕ ДОЛЖЕН (SHALL NOT) превращаться в скрытый drop coverage, duplicate execution или бесконтрольное размножение ad hoc harness code.

#### Scenario: PoolRuns residual monolith is split into reviewable scenario families
- **GIVEN** `frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx` остаётся одним из главных single-file runtime tails
- **WHEN** команда завершает этот change
- **THEN** route-stage scenarios перераспределены по нескольким checked-in test files с общими helpers
- **AND** новый heavy inventory продолжает покрывать эти scenarios без duplicate execution

#### Scenario: PoolMasterData residual monolith is split into reviewable scenario families
- **GIVEN** `frontend/src/pages/Pools/__tests__/PoolMasterDataPage.test.tsx` остаётся одним из главных single-file runtime tails
- **WHEN** команда завершает этот change
- **THEN** multi-zone/bootstrap/sync scenarios перераспределены по нескольким checked-in test files с общими helpers
- **AND** новый heavy inventory продолжает покрывать эти scenarios без duplicate execution
