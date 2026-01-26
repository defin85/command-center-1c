## MODIFIED Requirements
### Requirement: Полный рендер common flags `ibcmd` и явное разделение DBMS/IB auth
Система ДОЛЖНА (SHALL) оптимизировать UX отображения общего набора driver-level флагов `ibcmd` так, чтобы:
- секция `Driver options` оставалась управляемой при большом количестве полей;
- “частые” поля были доступны без скролла на несколько экранов;
- редкие/advanced поля не мешали основному сценарию.

#### Scenario: Driver options не превращаются в “простыню”
- **GIVEN** пользователь открыл `DriverCommandBuilder` для `driver=ibcmd`
- **WHEN** UI отображает `Driver options`
- **THEN** поля сгруппированы и доступны через сворачиваемые блоки (минимум: `Auth context`, `Connection`, `Execution`, `Advanced`)
- **AND** по умолчанию показаны только “common” и/или заполненные поля, а “advanced” скрыты до явного действия пользователя

### Requirement: DBMS креды не вводятся в DriverCommandBuilder
Система ДОЛЖНА (SHALL) не отображать в `DriverCommandBuilder` поля для DBMS кредов (`connection.offline.db_user/db_pwd`) и не позволять вводить/сохранять их в UI state/shortcuts.

#### Scenario: DBMS креды скрыты и помечены как “resolved”
- **GIVEN** пользователь открыл `DriverCommandBuilder` для `driver=ibcmd`
- **WHEN** UI отображает `Driver options`
- **THEN** `connection.offline.db_user` и `connection.offline.db_pwd` не отображаются как поля ввода
- **AND** UI показывает подсказку, что DBMS креды резолвятся через credential mapping/секреты

### Requirement: Shortcuts сохраняют воспроизводимую конфигурацию команды
Система ДОЛЖНА (SHALL) сохранять ярлык `ibcmd` так, чтобы он воспроизводил выбранную конфигурацию команды, включая:
- `command_id`
- `driver options` (connection/timeout/ib_auth.strategy/auth_database_id, без секретов)
- `params`
- `additional_args` (или эквивалентное поле ввода `args_text`)

#### Scenario: Save shortcut включает driver options/params/args
- **GIVEN** пользователь настроил `DriverCommandBuilder` для `driver=ibcmd`
- **WHEN** пользователь нажимает `Save shortcut`
- **THEN** ярлык при последующей загрузке восстанавливает `command_id`, `driver options`, `params` и `additional_args`

### Requirement: Shortcuts валидируются при изменении схемы
Система ДОЛЖНА (SHALL) валидировать загружаемый ярлык относительно текущей effective schema и предпринимать действие, если схема изменилась:
- показать пользователю, какие поля устарели/неизвестны/некорректны;
- предложить автоматическую нормализацию (drop неизвестных полей, применение defaults) или ручное исправление.

#### Scenario: Загрузка ярлыка с устаревшими полями
- **GIVEN** ярлык был сохранён до изменения `driver_schema`/`command schema`
- **WHEN** пользователь загружает ярлык
- **THEN** UI показывает предупреждение о несовместимости
- **AND** UI предлагает “Apply migrated config” или перейти к ручному редактированию

