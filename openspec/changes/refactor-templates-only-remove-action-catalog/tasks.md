## 1. Specs & Contracts
- [ ] 1.1 Обновить delta-specs для capabilities: `operation-definitions-catalog`, `operation-templates`, `extensions-plan-apply`, `extensions-overview`, `extensions-action-catalog`, `ui-action-catalog-editor`, `execution-plan-binding-provenance`, `command-result-snapshots`.
- [ ] 1.2 Зафиксировать platform-level decommission `action_catalog` и стабильный decommission-контракт `HTTP 404` + `error.code=NOT_FOUND` для `GET /api/v2/ui/action-catalog/`.
- [ ] 1.3 Обновить OpenAPI: удалить endpoint `ui/action-catalog`, убрать `surface=action_catalog`, перевести `extensions.plan/apply` на manual-operations контракт.
- [ ] 1.4 Добавить явный OpenAPI-контракт для preferred bindings (`GET|PUT|DELETE /api/v2/extensions/manual-operation-bindings/...`) и error matrix.
- [ ] 1.5 Регенерировать frontend API типы/клиент после обновления OpenAPI.

## 2. Backend: Domain Decommission
- [ ] 2.1 Удалить `SURFACE_ACTION_CATALOG` из модели `OperationExposure` и всех активных write/read веток.
- [ ] 2.2 Добавить миграцию hard delete для legacy `surface=action_catalog` exposures + cleanup orphan definitions без удаления historical references plan/execution/snapshot.
- [ ] 2.3 Удалить runtime helpers и резолверы action-catalog (`build_effective_action_catalog_payload`, reserved action resolvers, related marker logic).
- [ ] 2.4 Удалить backend wiring/serializers/views для `GET /api/v2/ui/action-catalog/`.

## 3. Backend: Manual Operations Layer
- [ ] 3.1 Ввести hardcoded registry manual operations (первичный scope: `extensions.sync`, `extensions.set_flags`; `extensions.list` удалить).
- [ ] 3.2 Перевести `extensions.plan/apply` на единый request contract с `manual_operation` и template-based resolve.
- [ ] 3.3 Реализовать deterministic resolve: `template_id` override -> иначе tenant preferred binding -> иначе fail-closed ошибка (в т.ч. stale binding после rename/delete alias).
- [ ] 3.4 Добавить fail-closed template/manual-operation compatibility validation.
- [ ] 3.5 Полностью удалить `action_id` path и legacy ambiguous-action логику.
- [ ] 3.6 Обновить operation metadata: заменить action-поля на `manual_operation`, `template_id`, `result_contract`, `mapping_spec_ref`.
- [ ] 3.7 Отклонять `extensions.apply` для legacy-планов старого формата (`PLAN_INVALID_LEGACY`) по детерминированному критерию metadata-контракта, без попыток адаптации.

## 4. Backend: Persist Bindings + Result Contract Mapping
- [ ] 4.1 Добавить tenant-scoped persistent store preferred template bindings per manual operation.
- [ ] 4.2 Добавить API read/write для preferred manual operation bindings.
- [ ] 4.3 Зафиксировать единый result contract слой для manual operations и привязку к mapping spec.
- [ ] 4.4 Пиновать mapping contract/version в plan metadata, чтобы completion не зависел от произвольного post-enqueue изменения настроек.

## 5. Frontend: Templates/Extensions/Databases
- [ ] 5.1 `/templates`: убрать surface switch (`all|action_catalog`) и action controls; оставить templates-only registry.
- [ ] 5.2 Сделать editor templates универсальным по executor kinds (`ibcmd_cli`, `designer_cli`, `workflow`) с ориентацией на driver schemas.
- [ ] 5.3 `/extensions`: внедрить manual operations UI (`manual_operation`, template selection, runtime input) без action-catalog controls.
- [ ] 5.4 `/databases`: запускать manual operations напрямую из экрана (без action-catalog drawer списка), используя тот же template-based pipeline.
- [ ] 5.5 Реализовать UI для preferred template binding per manual operation (просмотр/изменение, fallback логика резолва).
- [ ] 5.6 Удалить frontend hooks/types/pages, завязанные на action catalog runtime.

## 6. Migration, Docs, Validation
- [ ] 6.1 Обновить docs/runbooks/roadmaps/release notes на templates-only + manual-operations модель.
- [ ] 6.2 Удалить или переписать тесты и фикстуры action-catalog capability.
- [ ] 6.3 Добавить/обновить тесты для decommission (`404`, unsupported surface, legacy request reject).
- [ ] 6.4 Добавить/обновить тесты compatibility matrix manual operation <-> template.
- [ ] 6.5 Добавить/обновить тесты preferred template bindings и resolve order.
- [ ] 6.6 Добавить/обновить тесты result-contract mapping и snapshot completion metadata pinning.
- [ ] 6.7 Добавить/обновить тесты alias lifecycle (`rename/delete` -> stale binding -> `MISSING_TEMPLATE_BINDING`).
- [ ] 6.8 `openspec validate refactor-templates-only-remove-action-catalog --strict --no-interactive`.
