## 1. Phase 1: Contract и моделирование
- [ ] 1.1 Зафиксировать phase-1 scope change: explicit branching contract, runtime semantics и minimal canonical authoring path без full migration wizard.
- [ ] 1.2 Зафиксировать в spec и DAG schema новые analyst-facing node types: `decision`, `gateway_exclusive`, `gateway_inclusive`.
- [ ] 1.3 Зафиксировать typed `branch edge contract` для outgoing branches, включая `default` branch, supported operators, source-path resolution и fail-closed validation rules.
- [ ] 1.4 Зафиксировать compatibility contract для legacy `condition`-node и raw `edge.condition` как inspectable/executable read-only compatibility path.

## 2. Phase 1: Backend runtime и валидация
- [ ] 2.1 Обновить backend workflow schema/serializers/validator под новые node types и persisted branch edge payload без silent fallback на handle ids или edge labels.
- [ ] 2.2 Реализовать runtime semantics для `Decision Task`, `Exclusive Gateway` и `Inclusive Gateway`, включая activated-branch provenance и fail-closed ambiguous/no-match handling.
- [ ] 2.3 Обновить run lineage/diagnostics/read-model так, чтобы они показывали evaluated decision outputs, matched branches, default-path usage и downstream active-branch provenance.

## 3. Phase 1: Frontend canonical path
- [ ] 3.1 Обновить workflow designer palette/canvas/property editor под `Decision Task`, `Exclusive Gateway`, `Inclusive Gateway` и first-class branch edge editing.
- [ ] 3.2 Убрать misleading primary UX у текущего `Decision Gate`: legacy `condition`-узлы и raw edge conditions должны отображаться как compatibility-only/read-only path с явным static migration handoff, но без обязательного conversion wizard в рамках этого change.
- [ ] 3.3 Обновить persisted DAG adapter и frontend types так, чтобы branch semantics сохранялись как explicit contract, а не как неструктурированный edge label.

## 4. Проверки и документация
- [ ] 4.1 Добавить backend tests на schema validation, exclusive/inclusive routing, ambiguous matches, default branch, activated-branch fan-in и compatibility execution legacy workflows.
- [ ] 4.2 Добавить frontend tests на designer authoring flow, edge contract editing, read-only compatibility UX и correct DAG serialization.
- [ ] 4.3 Обновить analyst/operator docs по workflow modeling: `Decision Task -> Gateway`, branching contract, compatibility limitations и scope границу phase 1.
- [ ] 4.4 Прогнать `openspec validate add-workflow-gateway-branching-contract --strict --no-interactive` и релевантные contract/type validations.
