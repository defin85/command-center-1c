## 1. Specs & Contracts
- [ ] 1.1 Обновить delta-specs для capabilities: `operation-definitions-catalog`, `operation-templates`, `extensions-plan-apply`, `extensions-overview`, `extensions-action-catalog`, `ui-action-catalog-editor`.
- [ ] 1.2 Зафиксировать decommission `action_catalog` как полное удаление runtime/management контракта (без fallback).
- [ ] 1.3 Обновить OpenAPI: удалить `GET /api/v2/ui/action-catalog/`, убрать `surface=action_catalog`, перевести `extensions.plan/apply` на template-based request/response shape.
- [ ] 1.4 Регенерировать frontend API типы и клиент после обновления OpenAPI.

## 2. Backend: Unified Domain Model
- [ ] 2.1 Удалить поддержку `surface=action_catalog` из валидации и API write/read path в `operation-catalog`.
- [ ] 2.2 Перевести `OperationExposure` на template-only contract и добавить миграцию для удаления/деактивации legacy action-catalog данных.
- [ ] 2.3 Удалить runtime helpers, резолвящие executor из action catalog (`build_effective_action_catalog_payload` и связанные reserved-capability резолверы).
- [ ] 2.4 Удалить endpoint `GET /api/v2/ui/action-catalog/` и все backend wiring/сериализаторы для него.

## 3. Backend: Extensions Plan/Apply
- [ ] 3.1 Ввести template-based request contract для `extensions.*` (обязательный `template_id`, capability-aware runtime input).
- [ ] 3.2 Реализовать fail-closed validation совместимости `template_id` и выбранной ручной операции (`extensions.sync`, `extensions.set_flags`).
- [ ] 3.3 Обеспечить deterministic mapping runtime input -> effective executor params только через template payload.
- [ ] 3.4 Полностью удалить `action_id` runtime path и ambiguous-action логику из `extensions.plan/apply`.
- [ ] 3.5 Обновить plan persistence/provenance metadata под template-based execution источник.

## 4. Frontend: Templates/Extensions/Databases
- [ ] 4.1 `/templates`: убрать surface switch (`all|action_catalog`), mixed rows и controls `New Action`; оставить templates-only registry.
- [ ] 4.2 Переиспользовать существующий editor shell как templates-only editor flow (без action-catalog ветки).
- [ ] 4.3 `/extensions`: убрать Action Catalog controls, добавить templates-only manual operations contract с выбором template и runtime input.
- [ ] 4.4 `/databases`: убрать запуск extensions через action list/drawer action catalog; использовать template-based manual path.
- [ ] 4.5 Удалить frontend hooks/types/pages, завязанные на action catalog runtime (`useActionCatalog`, action-catalog launch flows и т.д.).

## 5. Cleanup & Docs
- [ ] 5.1 Удалить/обновить operator docs и runbooks, где фигурируют `/templates?surface=action_catalog` и `ui/action-catalog`.
- [ ] 5.2 Обновить roadmap/release notes, чтобы templates-only модель была описана как единственная.
- [ ] 5.3 Удалить устаревшие action-catalog тестовые фикстуры/утилиты, не используемые после cutover.

## 6. Validation
- [ ] 6.1 `openspec validate refactor-templates-only-remove-action-catalog --strict --no-interactive`.
- [ ] 6.2 Прогнать backend тесты: `operation-catalog`, `extensions-plan-apply`, migration/cutover сценарии decommission.
- [ ] 6.3 Прогнать frontend unit/browser тесты для `/templates`, `/extensions`, `/databases` в templates-only режиме.
- [ ] 6.4 Проверить, что legacy action-catalog запросы fail-closed и не исполняются.
