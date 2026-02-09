## 1. Spec Alignment
- [x] 1.1 Обновить `operation-templates`: зафиксировать `/templates` как один список exposures, где `surface` — фильтр, а не page-level режим.
- [x] 1.2 Обновить `ui-action-catalog-editor`: staff-only action editing происходит в том же list+editor flow из общего реестра.

## 2. Frontend IA Refactor (`/templates`)
- [x] 2.1 Перестроить page shell в “Operation Exposures” с одной таблицей и одним toolbar.
- [x] 2.2 Добавить фасет `surface` (`all/template/action_catalog` для staff, только `template` для non-staff).
- [x] 2.3 Добавить явное отображение `surface` в строках списка (column/badge), чтобы mixed-list был понятен.
- [x] 2.4 Сохранить единый `OperationExposureEditorModal` для create/edit в обоих surfaces.
- [x] 2.5 Для `surface=all` обеспечить явный выбор поверхности при создании (или детерминированное правило выбора), без второго page-level flow.
- [x] 2.6 Синхронизировать selected `surface` с query-параметром URL.
- [x] 2.7 Гарантировать, что non-staff не инициирует action-catalog management запросы.
- [x] 2.8 Для `capability=extensions.set_flags` в unified action editor добавить явный selector поля `target_binding.extension_name_param` по `params_by_name` выбранного `command_id`.
- [x] 2.9 Гарантировать, что binding-поле настраивается в action editor (capability-specific), а не через `command-schemas` экран.

## 3. Tests
- [x] 3.1 Обновить browser tests под единый list UX (без сценариев “режим страницы template/action”).
- [x] 3.2 Проверить deep-link сценарии `?surface=all|template|action_catalog` для staff.
- [x] 3.3 Проверить fallback/guard для non-staff (`action_catalog` и `all` неактивны и не инициируют action management запросы).
- [x] 3.4 Проверить create/edit flow для action из общего списка (включая mixed-surface представление).
- [x] 3.5 Проверить `extensions.set_flags` binding UX в `/templates`:
- [x] 3.5.1 Поле `target_binding.extension_name_param` отображается как selector при выбранном `command_id`.
- [x] 3.5.2 Выбранный параметр сохраняется и попадает в payload action catalog.

## 4. Validation
- [x] 4.1 `openspec validate refactor-step-1-unified-exposures-single-list-ui --strict --no-interactive`
- [x] 4.2 Прогнать релевантные frontend тесты (`/templates` routing/list/editor/RBAC).
