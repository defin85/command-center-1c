## 1. Specs & Contracts
- [x] 1.1 Обновить delta-specs для `command-result-snapshots`, `extensions-action-catalog`, `ui-action-catalog-editor` под hardening-контур.
- [x] 1.2 Очистить OpenAPI от legacy Action Catalog component-схем и проверить, что decommission-контракт endpoint остаётся стабильным (`404`, `NOT_FOUND`).
- [x] 1.3 Регенерировать frontend API client/types после очистки OpenAPI.

## 2. Backend: Snapshot Completion Hardening
- [x] 2.1 Реализовать в completion pipeline применение pinned `mapping_spec_ref` (`mapping_spec_id` + `mapping_spec_version`) вместо неявного текущего mapping.
- [x] 2.2 Добавить fail-closed обработку edge-case, когда pinned mapping недоступен/несогласован с metadata (диагностика сохраняется, raw snapshot не теряется).
- [x] 2.3 Добавить явную валидацию normalized/canonical payload против `result_contract` с сохранением validation diagnostics.
- [x] 2.4 Добавить/обновить backend тесты на post-enqueue change mapping, missing pinned mapping и invalid contract payload.

## 3. Decommission Hygiene: API/Frontend
- [x] 3.1 Удалить из OpenAPI legacy schemas (`ActionCatalogResponse`, `ActionCatalogExtensions`) и любые мёртвые ссылки на них.
- [x] 3.2 Удалить из generated frontend моделей/action exports соответствующие legacy типы после codegen.
- [x] 3.3 Проверить, что в рабочих frontend flow нет runtime-зависимостей от этих legacy типов.

## 4. Tests & Docs Hardening
- [x] 4.1 Переписать browser tests (`/templates`, `/extensions`, `/databases`) с templates-only ожиданиями без `surface=action_catalog`.
- [x] 4.2 Переписать/удалить backend тестовые фикстуры, завязанные на `SURFACE_ACTION_CATALOG`.
- [x] 4.3 Обновить операторские и release-docs, убрать legacy route `/templates?surface=action_catalog` из актуальных инструкций.
- [x] 4.4 Добавить регрессионные проверки, что UI не вызывает `/api/v2/ui/action-catalog/` в штатных сценариях.

## 5. Validation
- [x] 5.1 `openspec validate refactor-templates-only-cutover-hardening --strict --no-interactive`.
- [x] 5.2 Точечно зафиксировать результаты проверки релевантных тестовых наборов (backend + browser) для изменённых областей.
