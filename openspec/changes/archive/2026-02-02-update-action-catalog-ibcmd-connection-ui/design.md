# Design: `executor.connection` и единый UX ошибок для `ibcmd_cli`

## Контекст
Редактор `ui.action_catalog` уже умеет настраивать `executor.kind/driver/command_id/params/...`, но не экспонирует и не валидирует `executor.connection`. При этом в UI выполнения действий расширений и в мастере операций есть разный уровень "дружелюбности" ошибок preflight для `ibcmd_cli`.

## Решение (MVP)
1. **`executor.connection` как UI-контракт**: хранить connection override в `ui.action_catalog.extensions.actions[].executor.connection` (произвольный JSON object), и маппить его в `ExecuteIbcmdCliOperationRequest.connection` при запуске.
2. **Guided editor**: показывать блок `Connection` только для `executor.kind=ibcmd_cli`. Поля минимум:
   - `remote` (string),
   - `pid` (number),
   - `offline.*` (подмножество, достаточное для offline сценариев и preflight: `config`, `data`, `dbms`, `db_server`, `db_name`).
   Секреты (`db_user/db_pwd`) в UI не отображаются и не сохраняются.
3. **Defaulting**: перед preview/execute для `ibcmd_cli` и `scope=per_database` обеспечивать явный режим подключения. Если не задано ни `remote`, ни `pid`, ни `offline`, добавлять `connection.offline = {}`.
4. **Единый UX ошибок**: выделить общий обработчик, который по `error.code` строит сообщение/модалку. Для `OFFLINE_DB_METADATA_NOT_CONFIGURED` — показывать actionable инструкцию, идентичную мастеру операций.

## Альтернативы
- Полная замена editor modal на `DriverCommandBuilder`. Плюсы: максимальная унификация. Минусы: существенный рефактор модалки и более высокий риск регрессий. Оставляем как возможный follow-up после MVP.

## Риски и смягчение
- **Дивергенция полей connection**: минимизируем через переиспользование общих типов/утилит и единый handler defaulting.
- **Сохранение "мусора" в connection**: локальная валидация подтверждает, что `connection` — объект; backend остаётся fail-closed на этапе effective-catalog/execute.

