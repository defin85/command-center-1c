## ADDED Requirements
### Requirement: `/decisions` MUST быть task-first workspace с shareable route context
Система ДОЛЖНА (SHALL) поддерживать `/decisions` как stateful analyst workspace, где primary authoring context остаётся адресуемым, а основной путь считывается без знания всей внутренней модели платформы.

Default route path ДОЛЖЕН (SHALL):
- синхронизировать selected database, selected decision revision и snapshot filter mode с URL;
- иметь устойчиво подписанный database selector;
- выделять один primary authoring CTA;
- уводить secondary import/diagnostic controls в более слабую визуальную иерархию;
- показывать metadata/provenance/raw diagnostics через explicit progressive disclosure, а не как доминирующий default content.

#### Scenario: Deep link восстанавливает decision workspace context
- **GIVEN** аналитик открыл `/decisions` с query params выбранной базы, revision и snapshot mode
- **WHEN** страница инициализируется или пользователь возвращается через back/forward
- **THEN** UI восстанавливает тот же рабочий контекст
- **AND** не сбрасывает пользователя на произвольную базу или revision

#### Scenario: Основной authoring path не конкурирует с import и diagnostics
- **GIVEN** аналитик впервые открывает `/decisions`
- **WHEN** страница показывает основной workspace
- **THEN** один primary CTA для создания новой policy считывается как главный путь
- **AND** import/legacy/raw flows остаются доступными как secondary actions
- **AND** metadata-heavy diagnostics не доминируют над первым экраном по умолчанию
