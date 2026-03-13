## 1. Contract и моделирование
- [ ] 1.1 Зафиксировать в spec и DAG schema новые analyst-facing node types: `decision`, `gateway_exclusive`, `gateway_inclusive`.
- [ ] 1.2 Зафиксировать typed `branch edge contract` для outgoing branches, включая `default` branch, supported operators, source-path resolution и fail-closed validation rules.
- [ ] 1.3 Зафиксировать compatibility contract для legacy `condition`-node и raw `edge.condition`, включая guided migration и read-only compatibility surface.

## 2. Backend runtime и валидация
- [ ] 2.1 Обновить backend workflow schema/serializers/validator под новые node types и persisted branch edge payload без silent fallback на handle ids или edge labels.
- [ ] 2.2 Реализовать runtime semantics для `Decision Task`, `Exclusive Gateway` и `Inclusive Gateway`, включая activated-branch provenance и fail-closed ambiguous/no-match handling.
- [ ] 2.3 Обновить run lineage/diagnostics/read-model так, чтобы они показывали evaluated decision outputs, matched branches, default-path usage и downstream active-branch provenance.

## 3. Frontend authoring surface
- [ ] 3.1 Обновить workflow designer palette/canvas/property editor под `Decision Task`, `Exclusive Gateway`, `Inclusive Gateway` и first-class branch edge editing.
- [ ] 3.2 Убрать misleading primary UX у текущего `Decision Gate`: legacy `condition`-узлы и raw edge conditions должны отображаться только как compatibility-only/read-only path с явным migration handoff.
- [ ] 3.3 Обновить persisted DAG adapter и frontend types так, чтобы branch semantics сохранялись как explicit contract, а не как неструктурированный edge label.

## 4. Проверки и документация
- [ ] 4.1 Добавить backend tests на schema validation, exclusive/inclusive routing, ambiguous matches, default branch, activated-branch fan-in и compatibility execution legacy workflows.
- [ ] 4.2 Добавить frontend tests на designer authoring flow, edge contract editing, migration/read-only compatibility UX и correct DAG serialization.
- [ ] 4.3 Обновить analyst/operator docs по workflow modeling: `Decision Task -> Gateway`, branching contract, compatibility limitations и migration notes.
- [ ] 4.4 Прогнать `openspec validate add-workflow-gateway-branching-contract --strict --no-interactive` и релевантные contract/type validations.
