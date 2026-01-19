# Change: Добавить каталог действий расширений в RuntimeSetting

## Why
Зачем:
Нужно подключить существующие возможности Operations + Workflow к UI, чтобы управлять расширениями конфигурации 1С без хардкода привязок driver/command во фронтенде. Операторы должны иметь возможность настраивать, какие drivers/commands/workflows считаются "управлением расширениями".

## What Changes
Что меняется:
- Добавить новый ключ RuntimeSetting `ui.action_catalog`, который хранит JSON action catalog (первичный scope: секция `extensions`).
- Добавить API endpoint, который возвращает effective action catalog для текущего пользователя (фильтрация по RBAC, driver catalogs и окружению).
- Определить действия жизненного цикла расширений с разной семантикой deactivate vs delete и поддержкой bulk execution.
- Хранить snapshot расширений по каждой базе в Postgres (поддерживается) и обновлять его из настроенных действий sync/list.
- UI использует существующие Streams (Operations SSE) для отображения прогресса и результатов в реальном времени.

## Impact
Влияние:
- Затронутые спеки: `extensions-action-catalog` (new)
- Затронутый код (план): Orchestrator runtime settings + API v2, Frontend extensions UI
- Ломающих изменений нет (additive)
