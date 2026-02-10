## Context
Мы уже используем unified persistence (`operation_definition` + `operation_exposure`) и единый editor shell, но структура страницы `/templates` всё ещё ориентирована на переключение surfaces как отдельных “режимов”.

Цель шага 1: сделать в UI явный единый реестр exposures, не меняя backend contract.

## Goals
- Один список exposures на странице `/templates`.
- `surface` как фильтр списка, а не как page-level режим.
- Один modal editor для create/edit обоих surfaces.
- Предсказуемый URL-state и RBAC поведение.

## Non-Goals
- Изменение wire contract `/api/v2/operation-catalog/exposures/`.
- API-оптимизация (`include_definition`, server-side sort/search across all surfaces).

## UI Model
- Header: “Operation Exposures”.
- Toolbar: New, Search, Filters, `surface` facet.
- Table: смешанный набор строк (для staff), включая колонку `surface`.
- Editor: `OperationExposureEditorModal` c surface-specific полями внутри одного shell.

### Action binding UX (`extensions.set_flags`)
- Настройка `target_binding.extension_name_param` выполняется в unified action editor внутри `/templates`.
- Поле отображается как selector по `params_by_name` выбранного `command_id` (guided flow), чтобы оператор выбирал реальный command-level параметр из схемы команды.
- Binding остаётся capability-specific данными action exposure и не переносится в `command-schemas` (driver schema остаётся source-of-truth для доступных параметров).

## Data Flow (без API изменений)
- Staff:
  - использует существующий management flow, агрегируя exposures по текущему контракту;
  - для action rows подтягивает definitions текущим способом.
- Non-staff:
  - использует только template surface (`surface=template`);
  - action surface не доступен и не запрашивается.

## URL State
- `?surface=all|template|action_catalog`
- Staff default: `all`.
- Non-staff: принудительный fallback на `template` и очистка недопустимого значения в URL.

## RBAC
- UI не показывает action-management controls non-staff.
- UI не делает action-management запросы non-staff.
- Backend RBAC остаётся источником истины.

## Trade-offs
- На этом шаге возможен временный client-side merge/filter для mixed-list.
- Перфоманс и payload-оптимизация целенаправленно выносятся в шаг 2 (API контракт).
- Selector binding-поля добавляет зависимость editor UX от загруженной command schema, но снижает риск ручного ввода несуществующего параметра.
