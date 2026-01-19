# Change: Добавить UI редактор маппинга действий расширений (ui.action_catalog)

## Why
Сейчас маппинг “какие команды/воркфлоу управляют расширениями” настраивается через `RuntimeSetting ui.action_catalog`,
но его реально можно менять только через API (curl). Это неудобно и приводит к ошибкам (сложно валидировать руками, нет guided UX).

Нужен UI для staff-пользователей, который позволяет:
- добавлять/редактировать/удалять actions;
- выбирать executor (ibcmd_cli/designer_cli/workflow) и нужные ссылки (command_id/workflow_id);
- переключаться между guided формой и Raw JSON;
- видеть ошибки валидации с привязкой к полям.

## What Changes
- Добавить staff-only экран настроек “Action Catalog” с guided editor + Raw JSON toggle.
- Использовать существующий API `PATCH /api/v2/settings/runtime/ui.action_catalog/` для сохранения и серверную валидацию.
- Для guided editor использовать источники данных:
  - driver commands: `GET /api/v2/operations/driver-commands/?driver=...`
  - workflow templates: `GET /api/v2/workflows/list-templates/`
- Обновить документацию.

## Impact
- Затронутые спеки: `ui-action-catalog-editor` (new)
- Затронутый код (план): Frontend (страница настроек), Orchestrator API v2 (возможные вспомогательные endpoints/контракт)
- Ломающих изменений нет (additive)

