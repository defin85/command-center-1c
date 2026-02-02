# Change: Улучшить UX derived `ibcmd` connection (сводка+diff) и покрыть тестами профили подключения

## Why
После внедрения профиля подключения `ibcmd` на уровне базы (per database) появились два класса проблем:

1) **Недостаточная наблюдаемость в UI**:
   - при `scope=per_database` и derived connection пользователю видно лишь общее сообщение, но не видно *что именно* будет использовано для выбранных баз;
   - при mixed mode (часть баз remote, часть offline) нет сводки и понятного diff по отличающимся значениям.

2) **Недостаточное “code-first” доказательство поведения**:
   - отсутствуют изолированные Django-тесты на endpoint управления профилем подключения (`update-ibcmd-connection-profile`) и на ошибки derived-mode (`IBCMD_CONNECTION_PROFILE_INVALID`);
   - отсутствуют unit-тесты на UI редактирования профиля на странице `/databases`.

Также staff-only preview (`/api/v2/ui/execution-plan/preview/`) должен отражать происхождение DBMS metadata не только из профиля базы, но и fallback из `Database.metadata` (когда offline профиль не содержит `dbms/db_server/db_name`).

## Goals
- В Operations UI (Configure/Driver options) показывать **аггрегированную сводку** derived connection и **diff** по ключам, которые отличаются между выбранными базами.
- Улучшить **provenance** в staff-only preview, чтобы было видно fallback источники для DBMS metadata.
- Добавить недостающие **unit/integration тесты** (Django + Frontend) для ключевых сценариев.

## Non-goals
- Не менять модель данных профиля подключения (это отдельная тема).
- Не добавлять новые production endpoints “для превью” (в MVP делаем UI-резолв на основе уже доступных данных или существующего preview staff-only).
- Не хранить/передавать секреты через профиль подключения (DBMS/IB креды остаются через mappings/secret store).

## What changes
1) **Frontend Operations**:
   - при `driver=ibcmd`, `scope=per_database`, `override=false` показывать:
     - сводку: counts по effective mode (remote/offline), наличие mixed mode;
     - diff: список ключей connection, где значения отличаются по таргетам (с возможностью раскрыть детали).

2) **Frontend `/databases`**:
   - unit-тесты модалки редактирования `IBCMD connection profile` (валидации required полей, reset, сохранение payload).

3) **Orchestrator (tests + preview provenance)**:
   - Django-тесты на `POST /api/v2/databases/update-ibcmd-connection-profile/` (RBAC, tenant scope, set/reset, валидации, запрет секретов).
   - Django-тесты на `execute-ibcmd-cli` derived-mode:
     - missing/invalid profile -> `IBCMD_CONNECTION_PROFILE_INVALID`;
     - mixed mode допускается (remote + offline).
   - Улучшение binding provenance в staff-only preview, чтобы отражать fallback источники для `dbms/db_server/db_name` (профиль базы vs `Database.metadata`).

## Impact
- Затронутые компоненты: Frontend (Operations, Databases), Orchestrator (api_v2 preview, tests).
- Потенциальные риски: сложность UI при больших списках баз; нужно ограничение детализации/деградация UX для N >> 1.

## Acceptance criteria (high level)
- Operations UI: пользователь видит сводку и diff derived connection для выбранных баз (без секретов), включая mixed mode.
- Staff preview: bindings явно показывают fallback источники для `dbms/db_server/db_name`.
- Добавлены тесты, покрывающие основные сценарии (Django endpoint + derived errors, Frontend modal).

