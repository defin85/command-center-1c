# Change: Унифицировать настройку `connection` и UX ошибок `ibcmd_cli` между Action Catalog и Operations

## Why
Сейчас staff-only редактор `ui.action_catalog` (страница `/settings/action-catalog`) не даёт в guided-режиме настраивать `connection.remote/pid/offline.*` для `executor.kind=ibcmd_cli`, а локальная валидация каталога отклоняет поле `executor.connection` как неизвестное. Из-за этого:
- нельзя прозрачно задать явный режим подключения для `per_database` команд (`remote/pid/offline`),
- ошибки preflight (например `OFFLINE_DB_METADATA_NOT_CONFIGURED`) в UI действий расширений отображаются менее дружелюбно, чем в мастере операций.

## What Changes
- Guided editor `ui.action_catalog` получает блок настройки `executor.connection` для `executor.kind=ibcmd_cli` (remote/pid/offline.*), без ввода секретов.
- Локальная валидация draft (`validateActionCatalogDraft`) и трансформация form↔JSON начинают поддерживать `executor.connection`.
- Preview в редакторе `ui.action_catalog` и запуск действий расширений из `/databases` используют единый UX ошибок `ibcmd_cli` (включая `OFFLINE_DB_METADATA_NOT_CONFIGURED` с понятной инструкцией), согласованный с `NewOperationWizard`.
- Defaulting: если для `scope=per_database` не задано ни `remote`, ни `pid`, ни `offline`, UI перед запросом preview/execute обеспечивает **явный** режим подключения (минимум `connection.offline = {}`), чтобы не получать `MISSING_CONNECTION` на backend.

## Impact
- Affected specs: `ui-action-catalog-editor`, `extensions-action-catalog`.
- Affected code (ориентиры): `frontend/src/pages/Settings/*` (Action Catalog editor/preview/validation) и `frontend/src/pages/Databases/components/useExtensionsActions.tsx` (Run action).
- Backend/Contracts: без изменений (используются существующие `error.code` и существующее поле `executor.connection` как UI-контракт).

## Non-goals
- Не добавляем новые executor kinds и не меняем схему `ui.action_catalog` (v1) на backend (только расширяем поддерживаемый UI-ключ `executor.connection`).
- Не меняем правила preflight в API (контракт ошибок остаётся прежним).

