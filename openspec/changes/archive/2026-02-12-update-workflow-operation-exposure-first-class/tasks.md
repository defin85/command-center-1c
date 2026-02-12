## 1. Контракт workflow-ноды
- [x] 1.1 Добавить в workflow node schema/API поле `operation_ref` с режимами `alias_latest|pinned_exposure`.
- [x] 1.2 Оставить `template_id` как backward-compatible поле и описать deterministic правила миграции `template_id -> operation_ref`.
- [x] 1.3 Обновить frontend workflow designer/property editor: выбор template сохраняет `operation_ref` (включая exposure identity/revision).
- [x] 1.4 Добавить runtime setting `workflows.operation_binding.enforce_pinned` с default `false` и enforce-проверкой для create/update workflow.
- [x] 1.5 Реализовать lazy upgrade on save (`template_id -> operation_ref`) и read-path совместимость для legacy DAG.
- [x] 1.6 Добавить idempotent management command для опционального backfill существующих workflow DAG (`--dry-run` + apply mode).

## 2. Runtime резолв и fail-closed семантика
- [x] 2.1 Реализовать runtime resolver для двух режимов binding (`alias_latest`, `pinned_exposure`) без fallback на legacy path.
- [x] 2.2 Добавить fail-closed ошибки `TEMPLATE_DRIFT`/эквивалент для mismatch pinned exposure/revision.
- [x] 2.3 Обновить internal template API (`get-template`, `render-template`) для resolve по `template_exposure_id` при pinned execution.

## 3. Validation и publication gating
- [x] 3.1 Усилить write-time validation template exposure payload (`operation_type`, `template_data`, backend support).
- [x] 3.2 Применить те же правила на `validate`, `upsert`, `publish`, `sync-from-registry`.
- [x] 3.3 Обеспечить, что exposure с несовместимым payload не может перейти в `published`.

## 4. Wire contract и metadata
- [x] 4.1 Добавить `template_exposure_revision` в metadata enqueue/details для template-based операций.
- [x] 4.2 Обновить Go shared message model и worker pipeline для чтения `template_exposure_id` + `template_exposure_revision`.
- [x] 4.3 Обновить OpenAPI (public + internal) и generated clients/types.

## 5. UX рефакторинг `/templates` и модалки шаблона
- [x] 5.1 Переработать list `/templates`: явно показывать alias, `executor.kind`, `executor.command_id`, `template_exposure_id`, `template_exposure_revision`, publish status.
- [x] 5.2 Рефакторить modal editor шаблона в прозрачный guided flow: binding/executor параметры, source-of-truth для OperationDefinition и блок «что будет выполнено».
- [x] 5.3 Добавить inline подсказки/валидацию с маппингом backend `validation_errors` к полям формы и понятными причинами publish блокировок.
- [x] 5.4 Обновить frontend API/types и state handling под новые поля provenance (`template_exposure_id`, `template_exposure_revision`, `operation_type`).

## 6. Тесты и регрессии
- [x] 6.1 Добавить backend unit/integration тесты на `operation_ref` режимы, drift detection и fail-closed поведение.
- [x] 6.2 Добавить frontend/e2e тесты сохранения и редактирования workflow с `operation_ref`.
- [x] 6.3 Добавить frontend/e2e тесты usability/provenance для `/templates` list + modal (прозрачность binding и preview).
- [x] 6.4 Добавить contract/regression тесты для metadata/wire контрактов и internal template endpoints.
- [x] 6.5 Добавить тесты enforcement режима `enforce_pinned` (API validation + runtime reject alias-only execution).
- [x] 6.6 Добавить тесты lazy-upgrade и backfill command (dry-run/apply, idempotency).

## 7. Документация и валидация OpenSpec
- [x] 7.1 Обновить runbook/операционные инструкции по диагностике `TEMPLATE_DRIFT`.
- [x] 7.2 Обновить user-facing guide по `/templates`: как читать provenance полей и как диагностировать mismatch `OperationExposure/OperationDefinition`.
- [x] 7.3 Прогнать `openspec validate update-workflow-operation-exposure-first-class --strict --no-interactive`.

## 8. Явный data-flow для operation-ноды
- [x] 8.1 Расширить schema/API operation-node полем `io` (`input_mapping`, `output_mapping`, `mode`) без ломки legacy DAG без `io`.
- [x] 8.2 Реализовать validation `io` на write-time/publish-time: типы mapping, корректность path-format, запрет опасных target-path (reserved/system keys).
- [x] 8.3 Реализовать runtime-применение `io`:
  - input mapping перед `TemplateRenderer.render`,
  - output mapping после успешного выполнения operation,
  - fail-closed ошибка при `explicit_strict` и отсутствующем обязательном input-path.
- [x] 8.4 Обновить frontend workflow designer/property editor: удобный редактор `input_mapping`/`output_mapping` для operation-ноды с inline validation.
- [x] 8.5 Добавить backend/frontend/e2e тесты явного data-flow (success path, missing input-path, backward compatibility legacy implicit mode).
