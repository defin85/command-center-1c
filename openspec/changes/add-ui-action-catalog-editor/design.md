## Context (Контекст)
`ui.action_catalog` хранит JSON-каталог действий расширений и используется UI для отображения действий в `/databases`.
Backend уже валидирует shape (JSON Schema) и ссылки на `command_id`/`workflow_id` при обновлении runtime setting.

Не хватает только удобного UI для staff-пользователей.

## Goals / Non-Goals (Цели / Не цели)
- Goals:
  - Staff может безопасно редактировать `ui.action_catalog` без ручного curl.
  - Guided UI снижает вероятность ошибок: выбор из каталогов, подсказки, разумные дефолты.
  - Raw JSON остаётся доступным для power users.
  - Ошибки backend валидации отображаются в UI так, чтобы было понятно, что исправлять.
- Non-Goals:
  - Делать полноценный “конструктор операций” или менять driver catalog editor.
  - Делать RBAC/approval workflow поверх runtime settings (остаётся staff-only).

## UX / Flow (UX)
### Entry point
Новый экран в Settings, например:
- Route: `/settings/action-catalog`
- Название: “Action Catalog”
- Доступ: только staff

### Modes
1) Guided mode:
- Таблица/список actions с сортировкой и reorder.
- Drawer/Modal для редактирования одного action.
- Поля:
  - `id`, `label`, `contexts[]`
  - `executor.kind`
  - kind-specific поля (driver/command_id или workflow_id)
  - `mode`, `fixed.timeout_seconds`, `fixed.confirm_dangerous`
  - Advanced: `params`, `additional_args`, `stdin`

2) Raw JSON:
- JSON editor (с форматированием).
- Возможность “применить изменения” и вернуться в guided (если JSON валиден и соответствует schema).

### Validation and Errors
- Локально: валидность JSON (в raw), обязательные поля в guided.
- На save: backend PATCH возвращает `VALIDATION_ERROR` со списком сообщений вида `extensions.actions[0].executor.command_id: ...`.
  UI должен отобразить эти ошибки (списком + подсветка поля, если возможно).

## Data Sources
- Current catalog:
  - `GET /api/v2/settings/runtime/` (staff-only) + фильтрация `ui.action_catalog` по `key`.
- Save:
  - `PATCH /api/v2/settings/runtime/ui.action_catalog/`
- For pickers:
  - Commands: `GET /api/v2/operations/driver-commands/?driver=ibcmd|cli`
  - Workflows: `GET /api/v2/workflows/list-templates/` (is_template=true, is_active=true, is_valid=true)

## Risks / Edge Cases (Риски / крайние случаи)
- P0: Потеря данных при переключении guided ↔ raw. Нужны явные состояния “есть несохранённые изменения”, предсказуемая синхронизация между режимами и подтверждение при уходе со страницы.
- P0: Конкурирующие правки двумя staff (“last write wins”). Без версионирования/ETag легко перезаписать чужие изменения; нужен хотя бы diff/preview и явное обновление после Save.
- P0: Ошибки серверной валидации приходят путями с индексами массива (`extensions.actions[i]...`). После reorder/delete индексы “съезжают”, поэтому UI должен корректно сопоставлять ошибки и поля, иначе исправление становится практически невозможным.
- P0: Нельзя раскрывать `ui.action_catalog` non-staff. При реализации запросов важно не делать prefetch до проверки staff-прав в UI/роуте.
- P1: Невалидный `ui.action_catalog` приводит к “fail closed” для обычных пользователей (эффективный каталог становится пустым). Редактор должен явно объяснять staff, что конфигурация сломана, и показывать ошибки/причину.
- P1: Источники для pickers могут требовать отдельных permissions (особенно workflows). Нужны понятные fallback-сценарии (пустые списки + объяснение/инструкция), иначе guided-режим “ломается”.
- P1: Staff может настроить опасные команды. В guided-режиме нужны явные предупреждения/лейблы риска и аккуратное использование `fixed.confirm_dangerous` и таймаутов.
- P2: Schema строгая (`additionalProperties=false`, лимиты на поля). Без локальной валидации будут частые 400 на Save и плохой UX.
- P2: Нужны UI-тесты на основные сценарии (загрузка, переключение режимов, Save, отображение ошибок), иначе высок риск регрессий.

## Open Questions
- Нужно ли показывать “effective preview” (как это увидит текущий пользователь) прямо в редакторе?
- Нужен ли импорт/экспорт JSON в файл (download/upload)?
