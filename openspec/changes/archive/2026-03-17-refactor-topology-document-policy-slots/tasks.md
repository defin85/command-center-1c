## 1. Контракт и модель данных

- [x] 1.1 Зафиксировать в спеках `edge.metadata.document_policy_key` как lightweight topology selector для publication slot.
- [x] 1.2 Зафиксировать в спеках разделение `pool_workflow_binding.decisions[].decision_key` как identity reusable decision и `pool_workflow_binding.decisions[].slot_key` как уникальный binding slot для policy-bearing decisions.
- [x] 1.3 Зафиксировать slot-based preview/read-model contract вместо single `compiled_document_policy`.
- [x] 1.4 Зафиксировать machine-readable error/status codes для missing slot, duplicate slot, ambiguous coverage и legacy topology payload после cutover.

## 2. Backend runtime и remediation

- [x] 2.1 Перевести decision evaluation на one-time materialization slot map `slot_key -> compiled policy` для preview/create-run без перегрузки `decision_key`.
- [x] 2.2 Перевести compile `document_plan_artifact` на per-edge resolution `document_policy_key -> binding.slot_key map`.
- [x] 2.3 Обновить execution context / lineage / retry contract на slot-based snapshot.
- [x] 2.4 Убрать из shipped preview/run path runtime fallback на `edge.metadata.document_policy` и `pool.metadata.document_policy`.
- [x] 2.5 Определить phased remediation/backfill/cutover flow для перевода legacy topology policy в canonical decision revisions + binding slot refs + topology keys.

## 3. Frontend/operator surfaces

- [x] 3.1 Выполнить UI-рефакторинг `Topology Editor`: заменить legacy `document_policy` panel на edge slot assignment workspace.
- [x] 3.2 Добавить в `Topology Editor` first-class control для `document_policy_key` и coverage diagnostics относительно явного canonical binding context.
- [x] 3.3 Выполнить UI-рефакторинг `Bindings`: заменить low-level editing raw decision refs на analyst-friendly editing binding slot refs с отдельным `slot_key`.
- [x] 3.4 Явно показать в `Bindings` и preview/run surface, какие named slots pinned через `slot_key`, какие topology edges ими покрыты, где coverage отсутствует и где binding context ambiguous.
- [x] 3.5 Ввести blocking remediation state для topology/binding surfaces, если pool еще зависит от legacy topology policy или slot coverage неполный.

## 4. Проверка

- [x] 4.1 Добавить backend tests на one-time slot-map materialization, per-edge policy resolution, missing slot failure, duplicate `slot_key` rejection, legacy binding-shape compatibility, retry snapshot reuse и legacy payload rejection.
- [x] 4.2 Добавить frontend tests на slot-oriented `Bindings` с отдельным `slot_key`, explicit binding-context coverage diagnostics и совместимость `/decisions` как canonical authoring surface.
- [x] 4.3 Обновить API/contract tests для slot-based preview/read-model shape и pool binding refs c `slot_key`.
- [x] 4.4 Выполнить `openspec validate refactor-topology-document-policy-slots --strict --no-interactive`.
