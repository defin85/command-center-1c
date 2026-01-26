## ADDED Requirements

### Requirement: Полный рендер common flags `ibcmd` и явное разделение DBMS/IB auth
Система ДОЛЖНА (SHALL) рендерить в `DriverCommandBuilder` полный набор driver-level флагов `ibcmd` (раздел 4.10.2) из effective `driver_schema`, включая алиасы и описания.

Система ДОЛЖНА (SHALL) группировать поля так, чтобы пользователь явно видел разницу между:
- DBMS offline‑подключением (dbms/server/name/user/password),
- Infobase аутентификацией (user/password/strategy),
- прочими filesystem/служебными параметрами (data/temp/system/log-data/...).

#### Scenario: Поля DBMS и IB auth отображаются в разных группах
- **GIVEN** пользователь открыл `DriverCommandBuilder` для `driver=ibcmd`
- **WHEN** UI отображает `Driver options`
- **THEN** поля DBMS creds и IB creds не смешиваются в одном списке и имеют понятные подписи

### Requirement: UI ограничивает выбор `ib_auth.strategy=service`
Система ДОЛЖНА (SHALL) отображать и позволять выбрать `ib_auth.strategy=service` только если команда и пользователь удовлетворяют политике allowlist/RBAC.

В противном случае UI ДОЛЖЕН (SHALL) либо:
- скрывать опцию `service`, либо
- показывать её disabled с понятным объяснением (почему недоступно).

#### Scenario: Опция service недоступна для non-allowlist или dangerous команды
- **GIVEN** команда вне allowlist или `risk_level=dangerous`
- **WHEN** пользователь открывает `DriverCommandBuilder`
- **THEN** `ib_auth.strategy=service` недоступна в UI

