## MODIFIED Requirements

### Requirement: Connection по умолчанию берётся из профиля базы и допускает per-run override
Система ДОЛЖНА (SHALL) в UI запуска `ibcmd` (DriverCommandBuilder/мастер операций) использовать профиль подключения базы как источник connection по умолчанию для `scope=per_database`.

Профиль базы трактуется как “raw flags” и может включать:
- `remote` (SSH URL),
- `pid`,
- `offline.*`.

UI ДОЛЖЕН (SHALL):
- отображать derived connection, резолвленный per target из профилей выбранных баз,
- поддерживать per-run override connection (применяемый ко всем выбранным базам),
- корректно отображать mixed mode (если разные базы используют разные заполненные параметры),
- отображать `remote` как SSH URL (а не HTTP).

#### Scenario: Mixed mode отображается явно на основе заполненных полей
- **GIVEN** пользователь выбрал N баз с разными профилями (например, у части задан `remote`, у части `offline`)
- **WHEN** UI отображает секцию Connection
- **THEN** UI показывает, что connection будет отличаться per target (mixed mode)

