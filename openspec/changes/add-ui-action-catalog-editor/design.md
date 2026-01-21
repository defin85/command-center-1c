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
- P0: Доступ (leak prevention). `ui.action_catalog` нельзя раскрывать non-staff: backend ДОЛЖЕН (SHALL) отдавать 403, а UI не должен делать prefetch до проверки staff-прав.
- P0: Конкурирующие правки двумя staff (“last write wins”). Без ETag/версий легко перезаписать чужие изменения; минимум — показывать server snapshot + diff/preview, блокировать Reload при dirty и обновлять snapshot после Save.
- P0: Потеря данных при переключении guided ↔ raw. Нужен один источник истины (draft), явный индикатор Unsaved changes и предсказуемая синхронизация между режимами; предупреждение при уходе со страницы — улучшение, но не критично для MVP.
- P1: Серверная валидация отдаёт ошибки путями с индексами массива (`extensions.actions[i]...`). После reorder/delete индексы “съезжают”; минимум — показать список ошибок как есть, улучшение — попытаться сопоставить ошибки с action по `id` и/или подсветить поля в guided.
- P1: Источники данных для pickers (driver catalog / workflow templates) могут быть пустыми или недоступными (403/500). Нужны понятные fallback-сценарии (пустой список + сообщение, возможность исправить через Raw JSON), иначе guided-режим “ломается”.
- P1: Staff может настроить опасные команды. В guided-режиме нужны явные подсказки по risk_level и аккуратное использование `fixed.confirm_dangerous`/таймаутов; backend-валидация не гарантирует безопасность.
- P2: Строгость schema (`additionalProperties=false`, лимиты на поля) ведёт к частым 400 на Save без локальной валидации. Минимум — проверка JSON/object/catalog_version, улучшение — клиентская JSON Schema validation.
- P2: Регрессии UX. Нужны UI-тесты на основные сценарии (загрузка, переключение режимов, Save, отображение ошибок), иначе мелкие изменения легко ломают flow.

## Open Questions
- Нужно ли показывать “effective preview” (как это увидит текущий пользователь) прямо в редакторе?
- Нужен ли импорт/экспорт JSON в файл (download/upload)?
