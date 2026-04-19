# agent-repository-guidance Specification

## Purpose
TBD - created by archiving change add-codex-agent-productivity-foundation. Update Purpose after archive.
## Requirements
### Requirement: Репозиторий MUST публиковать canonical agent onboarding surface

Система ДОЛЖНА (SHALL) иметь stable agent-facing documentation surface в `docs/agent/INDEX.md`, объявленный canonical entry point для нового агента, начинающего работу из корня репозитория.

Supporting agent-facing docs, на которые опирается canonical onboarding surface, ДОЛЖНЫ (SHALL) жить в stable path `docs/agent/*`.

Canonical onboarding surface ДОЛЖЕН (SHALL) как минимум:
- объяснять, что это за проект;
- показывать major subsystems и ключевые каталоги;
- указывать entry points;
- ссылаться на canonical runbook и verification guide;
- указывать, где находятся OpenSpec/Beads workflow instructions;
- делать discoverable machine-readable tooling surfaces, используемые агентом.

#### Scenario: Новый агент ищет первую точку входа
- **GIVEN** агент впервые открыл репозиторий из project root
- **WHEN** он следует canonical agent onboarding surface
- **THEN** он получает достаточную картину проекта, структуры и entry points без необходимости угадывать authoritative document вручную
- **AND** onboarding surface явно обозначает себя как canonical entry point для agent-facing guidance

### Requirement: `openspec/project.md` MUST ссылаться на canonical agent guidance surface

Система ДОЛЖНА (SHALL) поддерживать `openspec/project.md` в синхронизации с canonical agent onboarding surface, чтобы OpenSpec project context не направлял агента в legacy onboarding documents как в primary entry points.

`openspec/project.md` ДОЛЖЕН (SHALL):
- ссылаться на `docs/agent/INDEX.md` как на canonical agent-facing entry point;
- перечислять текущие key entry points и guidance references, согласованные с canonical surface;
- не представлять legacy onboarding layers как равноправные primary entry points.

#### Scenario: OpenSpec project context не уводит агента в legacy onboarding path
- **GIVEN** агент начинает работу через OpenSpec workflow
- **WHEN** он читает `openspec/project.md`
- **THEN** он видит ссылку на текущий canonical agent-facing path
- **AND** не получает устаревший список key entry points, конфликтующий с canonical onboarding surface

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

### Requirement: Major code areas MUST иметь scoped agent guidance

Система ДОЛЖНА (SHALL) предоставлять scoped `AGENTS.md` для major code areas, где локальные entry points, validation paths и subsystem-specific constraints существенно отличаются от repo-wide defaults.

Минимальный monitored set ДОЛЖЕН (SHALL) включать:
- `frontend/`;
- `orchestrator/`;
- `go-services/`.

Scoped guidance НЕ ДОЛЖЕН (SHALL NOT) дублировать весь root `AGENTS.md`; он ДОЛЖЕН (SHALL) описывать только локальные дельты и subsystem-specific workflows.

#### Scenario: Агент работает из подсистемы и получает локальные правила
- **GIVEN** агент начинает работу из каталога `frontend/`, `orchestrator/` или `go-services/`
- **WHEN** instruction chain подхватывает ближайший scoped `AGENTS.md`
- **THEN** агент получает локальные entry points, verification commands и ограничения этой подсистемы
- **AND** не вынужден реконструировать subsystem workflow только по коду и общему root guidance

### Requirement: Репозиторий MUST публиковать architecture map и verification references для агента

Система ДОЛЖНА (SHALL) публиковать agent-oriented architecture map и verification references в stable, checked-in paths.

Architecture map ДОЛЖЕН (SHALL):
- описывать major runtimes и их ответственность;
- фиксировать allowed high-level call graph;
- указывать ключевые entry points и каталоги.

Verification references ДОЛЖНЫ (SHALL):
- описывать canonical run path;
- описывать canonical validation path для основных типов изменений;
- ссылаться на debug/runtime inventory и другие проверяемые tooling surfaces.

#### Scenario: Агент готовится к изменению и может быстро выбрать правильный verification path
- **GIVEN** агент понял, в какой подсистеме он будет менять код
- **WHEN** он открывает architecture map и verification references
- **THEN** он видит, какие рантаймы и проверки связаны с этим change
- **AND** не полагается на устные договорённости или устаревшие документы для выбора test/run path

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

