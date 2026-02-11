## 1. Release Readiness и миграционный контур
- [ ] 1.1 Зафиксировать Big-bang runbook для одного релиза: maintenance window, go/no-go критерии, rollback шаги.
- [ ] 1.2 Реализовать preflight проверки перед cutover (alias/uniqueness/referential consistency/permission parity readiness) с явными порогами fail (`mismatch=0` для критических проверок).
- [ ] 1.3 Подготовить backup/restore процедуру и dry-run прогон на staging с production-like данными.
- [ ] 1.4 Зафиксировать code-path gate (grep/tests), подтверждающий отсутствие runtime/internal/rbac обращений к `OperationTemplate` в switch-контуре.

## 2. Data model cutover (OperationExposure-only)
- [ ] 2.1 Добавить/подготовить exposure-ориентированные структуры для template RBAC и ссылок операций (`templates_operation_exposure_permissions`, `templates_operation_exposure_group_permissions`).
- [ ] 2.2 Выполнить backfill из legacy `OperationTemplate*`/FK ссылок в exposure-ориентированную модель, включая parity-сверки direct/group permissions.
- [ ] 2.3 Выполнить backfill operation metadata на `template_id`(alias)+`template_exposure_id` для template-based операций.
- [ ] 2.4 В этом же релизе удалить legacy таблицу `operation_templates`.
- [ ] 2.5 В этом же релизе удалить legacy таблицу `templates_operation_template_permissions`.
- [ ] 2.6 В этом же релизе удалить legacy таблицу `templates_operation_template_group_permissions`.
- [ ] 2.7 В этом же релизе удалить `batch_operations.template_id` FK/column и связанные индексы/constraints.

## 3. Runtime/API switch
- [ ] 3.1 Перевести workflow operation execution path на резолв template через `OperationExposure` alias (без `OperationTemplate.objects.get`).
- [ ] 3.2 Перевести internal template endpoints на exposure-based чтение/рендер.
- [ ] 3.3 Перевести template RBAC endpoints/effective-access/refs на exposure-ориентированный источник, сохранив внешний контракт API.
- [ ] 3.4 Реализовать fail-closed runtime semantics (`TEMPLATE_NOT_FOUND`, `TEMPLATE_NOT_PUBLISHED`, `TEMPLATE_INVALID`) без fallback на legacy projection.

## 4. Operations persistence и provenance
- [ ] 4.1 Перевести `BatchOperation`/enqueue/message metadata на template reference через exposure alias/identifier.
- [ ] 4.2 Обновить execution plan/bindings/details контракт так, чтобы provenance не зависел от `OperationTemplate` FK.
- [ ] 4.3 Зафиксировать строгий wire-контракт для post-cutover template-based операций: обязательные `template_id` и `template_exposure_id`.

## 5. Контракты, тесты и регрессии
- [ ] 5.1 Обновить OpenAPI и generated client types для нового metadata/provenance контракта при сохранении backward-compatible внешних полей.
- [ ] 5.2 Обновить backend/unit/integration тесты для cutover сценариев (RBAC, workflow execution, internal template API, enqueue/details).
- [ ] 5.3 Добавить регрессионные проверки, что код не читает/не пишет legacy `OperationTemplate` projection после cutover.

## 6. Валидация релиза
- [ ] 6.1 `openspec validate refactor-operation-exposure-bigbang-cutover --strict --no-interactive`.
- [ ] 6.2 Прогон целевых quality gates (backend tests + API regression + критические browser smoke flows).
- [ ] 6.3 Зафиксировать post-cutover checklist: data consistency, RBAC parity, отсутствие legacy runtime references.
