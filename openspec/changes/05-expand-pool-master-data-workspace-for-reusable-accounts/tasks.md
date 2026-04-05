## 0. Prerequisite Gate
- [ ] 0.1 Подтвердить, что `/pools/master-data` уже migrated на canonical multi-zone shell в `04-refactor-ui-platform-workflow-template-workspaces`, включая route-addressable active tab/remediation context и responsive fallback. Если prerequisite не landed, остановить реализацию `05` и продолжить работу в prerequisite change.

## 1. Shared Registry Helper Layer
- [ ] 1.1 Перевести operator-facing entity options и captions на registry `label` вместо raw `entity_type`.
- [ ] 1.2 Убрать string-specific bootstrap defaults и special-case exclusions; выражать page defaults через registry contract и page intent.
- [ ] 1.3 Добавить `gl_account` compatibility loader в token catalog и fail-closed coverage для registry-published token entities.
- [ ] 1.4 Обобщить bindings scope presentation/forms под registry fields, включая `chart_identity`.

## 2. Workspace Account Surfaces
- [ ] 2.1 Добавить в canonical `/pools/master-data` зоны `GLAccount` и `GLAccountSet`.
- [ ] 2.2 Реализовать list/detail authoring surfaces для `GLAccount` и draft/publish/revision surfaces для `GLAccountSet` через platform primitives.
- [ ] 2.3 Показать `chart_identity`, `config_name`, `config_version`, compatibility markers и revision status как явные operator-facing поля.
- [ ] 2.4 Показать capability-gated states: bootstrap-capable `GLAccount`, non-actionable profile state для `GLAccountSet`.

## 3. Catalog And Bootstrap Integration
- [ ] 3.1 Подключить `/pools/catalog` token picker к `master_data.gl_account.*.ref` через registry-driven catalog.
- [ ] 3.2 Расширить bootstrap import zone поддержкой `GLAccount` без появления generic mutating sync controls.

## 4. Verification
- [ ] 4.1 Добавить frontend unit tests на helper layer, новые workspace zones, binding scope fields, token picker и revision lifecycle.
- [ ] 4.2 Добавить browser tests на canonical shell integration, reload/deep-link restore и mobile-safe fallback без raw horizontal overflow.
- [ ] 4.3 Прогнать `npm --prefix frontend run lint`, `npm --prefix frontend run test:run`, `npm --prefix frontend run test:browser:ui-platform`, `npm --prefix frontend run build`.
- [ ] 4.4 Прогнать `openspec validate 05-expand-pool-master-data-workspace-for-reusable-accounts --strict --no-interactive`.
