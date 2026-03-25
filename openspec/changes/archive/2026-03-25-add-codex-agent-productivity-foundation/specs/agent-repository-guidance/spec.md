## ADDED Requirements

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

Система ДОЛЖНА (SHALL) поддерживать корневой `AGENTS.md` как краткий, практический repository contract для агента, а не как неограниченный dump всех workflow details.

Корневой `AGENTS.md` ДОЛЖЕН (SHALL):
- описывать repo layout и важные директории;
- перечислять canonical build/test/lint/run paths или ссылаться на них;
- фиксировать core constraints и do-not rules;
- описывать, что означает `done` и как проверять изменение;
- ссылаться на deeper agent-facing docs для длинных процедур;
- сохранять обязательные inline contracts из других capabilities, включая UI platform contract из `ui-frontend-governance`.

#### Scenario: Агент получает usable repository contract из root `AGENTS.md`
- **GIVEN** агент читает корневой `AGENTS.md` перед началом работы
- **WHEN** он строит план действий
- **THEN** он видит краткую repo map, обязательные инварианты и ссылки на deeper docs
- **AND** ему не требуется разбирать длинный смешанный документ, чтобы понять базовый workflow

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
