## ADDED Requirements

### Requirement: Репозиторий MUST публиковать product/domain onboarding map для агента

Система ДОЛЖНА (SHALL) иметь stable checked-in agent-facing asset для краткого product/domain onboarding.

Domain onboarding map ДОЛЖЕН (SHALL):
- объяснять ключевые operator outcomes и major product capabilities;
- перечислять основные domain entities и их роль в контуре `frontend -> api-gateway -> orchestrator -> worker -> 1C`;
- различать уже реализованные surfaces, активные change surfaces и roadmap/historical context;
- быть discoverable из canonical agent onboarding surface.

#### Scenario: Агенту нужно быстро понять, что делает продукт
- **GIVEN** новый агент открыл репозиторий и уже нашёл canonical onboarding path
- **WHEN** он открывает product/domain onboarding map
- **THEN** он получает короткую картину user-facing purpose, ключевых workflows и domain entities
- **AND** не вынужден реконструировать её только из README, OpenSpec и случайного чтения кода

### Requirement: Репозиторий MUST публиковать task routing matrix для типовых agent tasks

Система ДОЛЖНА (SHALL) иметь stable checked-in task routing asset для типовых task families.

Task routing matrix ДОЛЖЕН (SHALL):
- покрывать типовые task families как минимум для product/domain questions, frontend work, orchestrator work, go-services work, contracts/OpenSpec work и runtime-debug flows;
- указывать для каждой task family первые docs, кодовые entry points, verification commands и релевантные machine-readable surfaces;
- оставаться bounded reference asset, а не превращаться в исчерпывающий cookbook;
- быть discoverable из root onboarding guidance и canonical agent docs.

#### Scenario: Агент получает незнакомую задачу и выбирает первый рабочий маршрут
- **GIVEN** агент начинает задачу в незнакомой части репозитория
- **WHEN** он использует task routing matrix
- **THEN** он быстро находит первые релевантные docs, кодовые точки входа и verification path
- **AND** не тратит первые шаги на широкую ручную разведку по дереву репозитория

### Requirement: Freshness validation MUST проверять критичные guidance references семантически

Система ДОЛЖНА (SHALL) расширить freshness validation для authoritative agent guidance так, чтобы она проверяла не только наличие путей и строковых reference values, но и минимальную trustworthiness критичных guidance references.

Freshness validation ДОЛЖНА (SHALL):
- выполнять недеструктивные behavioral/smoke checks для критичных canonical commands, scripts и package entry points там, где существует дешёвый способ проверки;
- проверять semantic correspondence между authoritative docs и machine-readable runtime inventory для runtime names, ports и canonical verification surfaces;
- выдавать диагностический вывод, который показывает, какой guidance reference больше не подтверждается source-of-truth или smoke check.

#### Scenario: Команда в authoritative guidance больше не является рабочей reference point
- **GIVEN** authoritative doc всё ещё содержит существующий script path или command string
- **WHEN** freshness validation запускает semantic или smoke check для этого reference
- **THEN** validation завершается ошибкой, если reference больше не подтверждает заявленный workflow
- **AND** вывод показывает, какой именно guidance reference потерял доверие
