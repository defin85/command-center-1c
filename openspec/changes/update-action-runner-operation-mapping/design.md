# Design: Action Runner / operation mapping (MVP)

## Current state (evidence)
- Backend extensions plan выбирает action по `capability` и берёт первый match: `orchestrator/apps/api_v2/views/extensions_plan_apply.py` (`_get_extensions_action_from_catalog`).
- Backend update-time валидирует “duplicate reserved capability”: `orchestrator/apps/runtime_settings/action_catalog.py` (`validate_action_catalog_reserved_capabilities`).
- Frontend editor тоже блокирует дубли reserved capability: `frontend/src/pages/Settings/actionCatalog/actionCatalogValidation.ts`.
- В `Extensions` UI планирование set_flags жёстко зашито как `capability: 'extensions.set_flags'`: `frontend/src/pages/Extensions/Extensions.tsx`.
- В `Databases` UI runner уже исполняет выбранный action по `action.id` + `executor.kind`: `frontend/src/pages/Databases/components/useExtensionsActions.tsx`.

## Architecture drivers
- 1→N mapping: один semantic intent (`extensions.set_flags`) должен иметь несколько “вариантов запуска” (presets).
- Детерминизм и fail-closed: runtime behaviour не должен зависеть от порядка в JSON.
- Хороший UX: ошибки конфигурации должны быть явными, а не “Save disabled”.
- Эволюция: подготовить почву для schema-driven интерактивного ввода параметров и контекстных подстановок.

## Options

### Option A (Recommended, incremental): “Actions = presets”, `action_id` как первичный ключ
Сохраняем `ui.action_catalog` как список “публикуемых” действий (похоже на VS Code `commands` + `menus`: command ID уникален, а placement зависит от контекста). citeturn0search4turn0search5

- `action.id` — уникальный идентификатор (primary key для запуска).
- `action.capability` — semantic tag/intent (может повторяться).
- Runner в UI запускает по `action.id`.
- Backend endpoints, где раньше принимали только `capability`, принимают `action_id` (детерминизм). Если `capability` даёт несколько кандидатов — ошибка ambiguity.

Presets для set_flags:
- 3 actions с одинаковым `capability="extensions.set_flags"` и разными `executor.fixed.apply_mask`.
- UI может показать их как отдельные кнопки (“Apply active only”, …) или как Select.

### Option B: “выкинуть actions”, напрямую показывать driver operations из schema
Плюсы:
- Максимальная близость к драйверу; schema-driven формы проще.

Минусы:
- Потеря curated UX (label, placement/contexts, RBAC, dangerous confirmation).
- UI начнёт показывать “все команды драйвера”, что плохо масштабируется.

### Option C: Полный слой “Operations registry” (domain + driver) + actions как меню
Хорошая целевая модель, но больше объёма. Рекомендуется как follow-up после MVP (Option A), когда появится стабильный `ActionRunner` API и формат bindings.

## Recommended MVP
1) Разрешить несколько actions с одним `capability` (убрать uniqueness валидацию на update-time).
2) Сделать `action_id` обязательным для детерминизма там, где `capability` может быть неоднозначным.
3) Добавить presets для `extensions.set_flags` через `executor.fixed.apply_mask`.

## UI params: guided forms (follow-up)
Для интерактивного заполнения параметров по schema в UI можно использовать JSON Schema form подход (например, rjsf). citeturn0search0turn0search1
Важно учитывать интеграцию со стилями (AntD) и строгую “не разрушать пользовательский JSON” семантику (у нас уже есть Guided/Raw режимы в редакторе).

