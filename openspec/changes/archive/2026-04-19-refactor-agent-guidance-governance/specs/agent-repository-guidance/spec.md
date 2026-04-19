## MODIFIED Requirements

### Requirement: Корневой `AGENTS.md` MUST быть краткой практической картой репозитория

Система ДОЛЖНА (SHALL) поддерживать корневой `AGENTS.md` как компактный repo-wide invariant contract для агента, а не как смешанный документ, который одновременно пытается быть onboarding bundle, полным cookbook и локальным debug checklist.

Корневой `AGENTS.md` ДОЛЖЕН (SHALL):
- описывать repo layout и важные директории;
- фиксировать repo-wide constraints, do-not rules и source-of-truth pointers;
- перечислять canonical build/test/lint/run paths или ссылаться на них;
- описывать task-class completion model и как выбирать правильный verification/depth profile;
- ссылаться на routed/deeper agent-facing docs для длинных процедур и subsystem-specific workflows;
- сохранять обязательные inline contracts из других capabilities, включая UI platform contract из `ui-frontend-governance`.

Корневой `AGENTS.md` НЕ ДОЛЖЕН (SHALL NOT):
- требовать универсального широкого чтения всех onboarding assets для любой задачи;
- дублировать полный content routed docs, если этот content уже имеет stable authoritative path;
- смешивать repo-wide invariants с подробными route-specific walkthroughs без явного разделения.

#### Scenario: Агент получает компактный repo-wide contract вместо перегруженного mixed document
- **GIVEN** агент начинает работу из project root
- **WHEN** он читает корневой `AGENTS.md`
- **THEN** он быстро получает repo-wide invariants, source-of-truth pointers и route selection hints
- **AND** не обязан разбирать длинный смешанный документ, чтобы отличить core rules от task-specific procedures

## ADDED Requirements

### Requirement: Репозиторий MUST публиковать компактную precedence matrix для agent guidance

Система ДОЛЖНА (SHALL) иметь компактную repo-local precedence/conflict matrix для основных instruction surfaces, чтобы агент мог быстро разрешать конфликты между ними без повторного анализа всего guidance corpus.

Precedence matrix ДОЛЖНА (SHALL):
- различать как минимум root `AGENTS.md`, `docs/agent/*`, scoped `AGENTS.md`, `openspec/project.md` / `openspec/AGENTS.md`, checked-in repo skills и shared user-level skills;
- указывать, какой слой задаёт repo-wide invariants, какой слой задаёт routed workflow, а какой слой задаёт subsystem-local deltas;
- описывать fail-closed rule для ситуаций, где два слоя дают несовместимые указания одного уровня конкретности.

#### Scenario: Агент видит конфликт между root guidance и route-specific docs
- **GIVEN** агент нашёл два instruction source с несовместимыми указаниями
- **WHEN** он применяет repo-local precedence matrix
- **THEN** он быстро определяет, какой surface имеет приоритет для этой задачи
- **AND** не принимает решение только по неявной памяти о прошлых сессиях

### Requirement: Репозиторий MUST публиковать task-class completion profiles для agent work

Система ДОЛЖНА (SHALL) различать как минимум несколько классов agent work, для которых completion expectations и verification depth различаются по смыслу и стоимости.

Task-class completion profiles ДОЛЖНЫ (SHALL):
- покрывать как минимум `analysis/review`, `local change`, `delivery`;
- явно фиксировать минимальные expectations по evidence, verification и delivery actions для каждого класса;
- быть discoverable из root guidance и verification references;
- не заставлять небольшие analysis/review задачи проходить полный merge-ready delivery contract без необходимости.

#### Scenario: Небольшая аналитическая задача не навязывает delivery-grade workflow
- **GIVEN** пользователь просит analysis, review или guidance-only результат
- **WHEN** агент определяет class of work
- **THEN** он применяет соответствующий completion profile с нужной глубиной evidence
- **AND** не тащит в ответ неподходящие commit/push/Beads expectations только потому, что в репозитории существует более строгий delivery path

