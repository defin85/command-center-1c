# Release Notes — 2026-03-25

## add-topology-aware-template-execution-pack-authoring

### Что изменилось

- `/pools/execution-packs` теперь fail-close'ит новые и новые revision reusable execution packs, если topology-derived `party` или `contract` fields всё ещё используют concrete participant refs вместо topology-aware aliases.
- Canonical machine-readable diagnostic для этого producer path: `EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED`.
- `BindingProfileRevision` и pool attachment read-model теперь возвращают отдельный `topology_template_compatibility` summary, чтобы не смешивать structural slot coverage и semantic topology-aware readiness.
- Template-based `/pools/catalog` attachment/save/preview path теперь fail-close'ится на `EXECUTION_PACK_TEMPLATE_INCOMPATIBLE`, если execution pack structurally покрывает slot-ы, но semantic incompatible для topology-aware master-data contract.
- UI handoff нормализован: fix reusable logic делается через `/pools/execution-packs` и `/decisions`, а не через pool-local overrides.

### Operator actions

1. Для новых и новых revision reusable execution packs author'ите topology-derived participant bindings только через:
   - `master_data.party.edge.parent|child.<role>.ref`;
   - `master_data.contract.<contract_canonical_id>.edge.parent|child.ref`.
2. Если publish execution pack блокируется кодом `EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED`, откройте `/decisions`, выпустите topology-aware decision revision и затем повторите publish в `/pools/execution-packs`.
3. Если `/pools/catalog` или binding preview блокируется кодом `EXECUTION_PACK_TEMPLATE_INCOMPATIBLE`, не пытайтесь repair'ить это pool-local attachment-ом. Вернитесь в `/pools/execution-packs` и `/decisions`.
4. Перед create-run проверяйте template-based path через `POST /api/v2/pools/workflow-bindings/preview/`.

### Notes

- Этот rollout не переписывает автоматически historical execution packs с concrete participant refs.
- Static canonical tokens для `item` и `tax_profile` остаются допустимыми и не считаются incompatibility marker'ом этого change.
