## 1. Compatibility contract
- [x] 1.1 Зафиксировать в `pool-topology-templates` blocking compatibility distinction между structural slot coverage и topology-aware master-data readiness reusable execution pack.
- [x] 1.2 Зафиксировать в `pool-binding-profiles` authoring contract для canonical `/pools/execution-packs`: все новые и новые ревизии reusable execution packs fail-close'ятся, если topology-derived `party/contract` refs не переведены на topology-aware aliases.
- [x] 1.3 Зафиксировать stable machine-readable diagnostics и shared compatibility summary для producer и consumer path.
- [x] 1.4 Зафиксировать в `organization-pool-catalog` template-based pool assembly contract: `/pools/catalog` использует `slot_key -> organization_id` + topology-aware execution pack и fail-close'ится на incompatible reusable logic.

## 2. Implementation
- [x] 2.1 Добавить backend semantic validation на create/revise reusable execution packs для topology-derived `field_mapping` и `table_parts_mapping`.
- [x] 2.2 Добавить backend classification/read-model для reusable execution-pack compatibility с template structural slots и topology-aware master-data contract.
- [x] 2.3 Добавить blocking diagnostics и canonical handoff из `/pools/execution-packs` в `/decisions`, если selected decision revisions для topology-derived slots содержат concrete participant refs.
- [x] 2.4 Добавить blocking attach/preview/save diagnostics в `/pools/catalog` для template-based path, если selected execution-pack revision не проходит topology-aware compatibility.

## 3. Validation and docs
- [x] 3.1 Добавить backend tests на compatibility classification и fail-closed attach/preview path для template-oriented reusable execution packs.
- [x] 3.2 Добавить frontend/operator tests на blocking diagnostics и handoffs в `/pools/execution-packs` и `/pools/catalog`.
- [x] 3.3 Нормализовать docs/UI copy на `/pools/execution-packs` и убрать двусмысленные ссылки на `/pools/binding-profiles` в touched surfaces.
- [x] 3.4 Обновить runbook/release notes для new/revised template/execution-pack path без historical remediation claims.
- [x] 3.5 Прогнать `openspec validate add-topology-aware-template-execution-pack-authoring --strict --no-interactive`.
