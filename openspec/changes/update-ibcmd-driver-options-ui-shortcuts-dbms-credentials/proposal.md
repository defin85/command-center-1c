# Change: Оптимизация Driver options UI, shortcuts и DBMS кредов для ibcmd

## Why
Секция `Driver options` для `ibcmd` сейчас превращается в длинный “простынный” список общих флагов и не помещается в экран, из-за чего теряется управляемость и возрастает риск ошибки.

Дополнительно:
- В UI отображаются и могут вводиться креды СУБД (`connection.offline.db_user/db_pwd`), что плохо для безопасности и для воспроизводимости (креды не должны попадать в UI state/shortcuts).
- `Save shortcut` сохраняет только `command_id` и не запоминает `Driver options`/`params`/`args`, из-за чего ярлыки не воспроизводимы.
- Для `ibcmd` с `scope=per_database` операция может запускаться на нескольких базах, но для offline‑подключения нужны `--db-name` и прочие параметры, которые могут отличаться по таргетам; текущая модель “одна `connection.offline.*` на всю операцию” это не покрывает.

## What Changes
- UI `DriverCommandBuilder` для `ibcmd`:
  - оптимизирует отображение `Driver options` (группировка, сворачиваемые блоки, “показывать только заполненные/часто используемые”, поиск остаётся);
  - скрывает DBMS креды из формы (аналогично `ib_auth.user/password`) и показывает, что они резолвятся из маппинга/секретов;
  - делает `Save shortcut` воспроизводимым: сохраняет `command_id` + `driver options` + `params` + `args_text` (+ метаданные для валидации/миграции при изменении схемы).
- Orchestrator:
  - добавляет модель и API для маппинга CC пользователя → DBMS пользователя/пароля (аналогично `InfobaseUserMapping`), с поддержкой service‑аккаунта;
  - вводит правила резолва DBMS connection/creds для `ibcmd` per‑database (значения могут отличаться на каждом таргете) без передачи DBMS кредов из UI.
- Worker:
  - инжектит DBMS креды в `argv` на рантайме на основе маппинга и конкретного таргета (и продолжает инжектить IB креды по `ib_auth.strategy` как сейчас).
  - применяет “Configure” параметры к списку выбранных баз: одна операция → N задач, где часть offline‑параметров берётся per target (например `--db-name`), а часть — из общего шаблона (например `--dbms/--db-server`, если заданы).

## Impact
- Affected specs:
  - `ui-driver-command-builder` (layout/shortcuts/UX для driver options)
  - `command-schemas-driver-options` (семантика скрытых credential‑полей и правила резолва per‑target)
  - `execution-plan-binding-provenance` (прованенс резолва per‑target connection/creds)
  - **NEW** `dbms-credentials-mapping` (маппинг CC user ↔ DBMS creds)
- Affected code (будет в apply‑стадии):
  - `frontend/src/components/driverCommands/DriverCommandBuilder.tsx`
  - `orchestrator/apps/operations/models/driver_command_shortcut.py` + API v2 views/serializers
  - `orchestrator/apps/databases/models.py` (+ migrations) и связанные сервисы/эндпоинты
  - `go-services/worker` (резолв и инжект DBMS creds per target для ibcmd)
