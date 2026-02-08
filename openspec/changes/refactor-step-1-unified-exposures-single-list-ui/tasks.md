## 1. Spec Alignment
- [ ] 1.1 Обновить `operation-templates`: зафиксировать `/templates` как один список exposures, где `surface` — фильтр, а не page-level режим.
- [ ] 1.2 Обновить `ui-action-catalog-editor`: staff-only action editing происходит в том же list+editor flow из общего реестра.

## 2. Frontend IA Refactor (`/templates`)
- [ ] 2.1 Перестроить page shell в “Operation Exposures” с одной таблицей и одним toolbar.
- [ ] 2.2 Добавить фасет `surface` (`all/template/action_catalog` для staff, только `template` для non-staff).
- [ ] 2.3 Добавить явное отображение `surface` в строках списка (column/badge), чтобы mixed-list был понятен.
- [ ] 2.4 Сохранить единый `OperationExposureEditorModal` для create/edit в обоих surfaces.
- [ ] 2.5 Для `surface=all` обеспечить явный выбор поверхности при создании (или детерминированное правило выбора), без второго page-level flow.
- [ ] 2.6 Синхронизировать selected `surface` с query-параметром URL.
- [ ] 2.7 Гарантировать, что non-staff не инициирует action-catalog management запросы.

## 3. Tests
- [ ] 3.1 Обновить browser tests под единый list UX (без сценариев “режим страницы template/action”).
- [ ] 3.2 Проверить deep-link сценарии `?surface=all|template|action_catalog` для staff.
- [ ] 3.3 Проверить fallback/guard для non-staff (`action_catalog` и `all` неактивны и не инициируют action management запросы).
- [ ] 3.4 Проверить create/edit flow для action из общего списка (включая mixed-surface представление).

## 4. Validation
- [ ] 4.1 `openspec validate refactor-step-1-unified-exposures-single-list-ui --strict --no-interactive`
- [ ] 4.2 Прогнать релевантные frontend тесты (`/templates` routing/list/editor/RBAC).
