## ADDED Requirements

### Requirement: Репозиторий MUST публиковать execution-plan и review assets для длинной agent work

Система ДОЛЖНА (SHALL) иметь stable checked-in workflow assets для:
- long-running / multi-step implementation planning;
- code review / acceptance review.

Execution-plan asset ДОЛЖЕН (SHALL) задавать минимальный canonical template для:
- scope;
- assumptions;
- ordered steps;
- verification checkpoints;
- blockers/open questions.

Review asset ДОЛЖЕН (SHALL) задавать canonical checklist для bug/risk/regression-oriented review.

Оба assets ДОЛЖНЫ (SHALL) быть discoverable из agent-facing guidance, включая root `AGENTS.md` или canonical agent docs index.

#### Scenario: Агент стартует сложную multi-step задачу
- **GIVEN** пользователь просит длинную или архитектурно неоднозначную задачу
- **WHEN** агент ищет checked-in repository workflow для planning/review
- **THEN** он находит execution-plan template и review checklist в stable paths
- **AND** может использовать их без изобретения ad-hoc структуры на каждый новый change

### Requirement: Репозиторий MUST упаковывать повторяемые workflows как shared team skills

Система ДОЛЖНА (SHALL) хранить в `.agents/skills` shared team skills для repeatable workflows, которые иначе требуют длинных повторяющихся prompt instructions или ручного восстановления шагов.

Каждый checked-in skill ДОЛЖЕН (SHALL):
- описывать, что он делает и когда его использовать;
- иметь trigger phrases;
- фиксировать ожидаемые inputs/outputs;
- перечислять verification steps или success criteria;
- быть ограниченным одной практической задачей, а не охватывать “всё подряд”.

Минимальный initial scope ДОЛЖЕН (SHALL) покрывать наиболее дорогие и реально повторяемые repo workflows, связанные с debug/run/verification или change execution.

#### Scenario: Агент выполняет стандартный repo workflow через shared skill
- **GIVEN** пользователь просит типовой workflow, который уже повторялся в репозитории много раз
- **WHEN** агент ищет checked-in shared skill
- **THEN** он находит skill с понятным trigger description, bounded scope и verification steps
- **AND** не полагается на длинный одноразовый prompt как единственный способ воспроизвести workflow

### Requirement: Agent guidance MUST делать discoverable machine-readable repo tooling surfaces

Система ДОЛЖНА (SHALL) явно документировать в authoritative agent-facing guidance machine-readable и Codex-relevant repo tooling surfaces, которые нужны агенту для эффективной работы.

Минимальный required set ДОЛЖЕН (SHALL) включать:
- project-scoped `.codex/config.toml`, если он участвует в repo workflow;
- machine-readable runtime inventory (`debug/runtime-inventory.sh --json` или эквивалент);
- canonical script/package entry points, на которые агент должен опираться при run/test/verify flows.

#### Scenario: Агент ищет machine-readable inventory вместо ручного reverse engineering
- **GIVEN** агенту нужно быстро понять runtime topology или Codex-specific repo setup
- **WHEN** он следует authoritative agent-facing guidance
- **THEN** он видит явные ссылки на machine-readable inventory и project-scoped Codex config surfaces
- **AND** ему не приходится искать их только через случайный обзор дерева репозитория
