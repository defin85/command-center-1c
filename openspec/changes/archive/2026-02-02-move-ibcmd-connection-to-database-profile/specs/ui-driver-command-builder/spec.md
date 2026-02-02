# Delta: ui-driver-command-builder

## ADDED Requirements

### Requirement: Connection по умолчанию берётся из профиля базы и допускает per-run override
Система ДОЛЖНА (SHALL) в UI запуска `ibcmd` (DriverCommandBuilder/мастер операций) использовать профиль подключения базы как источник connection по умолчанию для `scope=per_database`.

UI ДОЛЖЕН (SHALL):
- отображать derived connection, резолвленный per target из профилей выбранных баз,
- поддерживать per-run override connection (применяемый ко всем выбранным базам),
- корректно отображать mixed mode (если разные базы используют разные режимы подключения),
- не требовать ввода `connection.pid` как часть “стандартного” сценария (PID может быть скрыт как advanced/debug).

#### Scenario: Mixed mode отображается явно
- **GIVEN** пользователь выбрал N баз с разными профилями подключения (`remote` и `offline`)
- **WHEN** UI отображает секцию Connection
- **THEN** UI показывает, что connection будет отличаться per target (mixed mode)
- **AND** UI не требует вручную унифицировать connection для запуска

#### Scenario: Per-run override отключает использование профилей без их изменения
- **GIVEN** пользователь выбрал N баз
- **WHEN** пользователь включает override connection (например задаёт `remote_url`) и запускает команду
- **THEN** override применяется при исполнении
- **AND** профиль баз остаётся неизменным

