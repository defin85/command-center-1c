## 1. Контракт и модель данных

- [ ] 1.1 Зафиксировать в спеках `edge.metadata.document_policy_key` как lightweight topology selector для publication slot.
- [ ] 1.2 Зафиксировать в спеках `pool_workflow_binding.decisions[].decision_key` как уникальный slot name для policy-bearing decisions.
- [ ] 1.3 Зафиксировать slot-based preview/read-model contract вместо single `compiled_document_policy`.
- [ ] 1.4 Зафиксировать machine-readable error/status codes для missing slot, duplicate slot, ambiguous coverage и legacy topology payload после cutover.

## 2. Backend runtime и remediation

- [ ] 2.1 Перевести decision evaluation на one-time materialization slot map `decision_key -> compiled policy` для preview/create-run.
- [ ] 2.2 Перевести compile `document_plan_artifact` на per-edge resolution `document_policy_key -> binding slot map`.
- [ ] 2.3 Обновить execution context / lineage / retry contract на slot-based snapshot.
- [ ] 2.4 Убрать из shipped preview/run path runtime fallback на `edge.metadata.document_policy` и `pool.metadata.document_policy`.
- [ ] 2.5 Определить phased remediation/backfill/cutover flow для перевода legacy topology policy в decision revisions + binding slots + topology keys.

## 3. Frontend/operator surfaces

- [ ] 3.1 Выполнить UI-рефакторинг `Topology Editor`: заменить legacy `document_policy` panel на edge slot assignment workspace.
- [ ] 3.2 Добавить в `Topology Editor` first-class control для `document_policy_key` и coverage diagnostics относительно явного canonical binding context.
- [ ] 3.3 Выполнить UI-рефакторинг `Bindings`: заменить low-level editing raw decision refs на analyst-friendly editing named publication slots.
- [ ] 3.4 Явно показать в `Bindings` и preview/run surface, какие named slots pinned, какие topology edges ими покрыты, где coverage отсутствует и где binding context ambiguous.
- [ ] 3.5 Ввести blocking remediation state для topology/binding surfaces, если pool еще зависит от legacy topology policy или slot coverage неполный.

## 4. Проверка

- [ ] 4.1 Добавить backend tests на one-time slot-map materialization, per-edge policy resolution, missing slot failure, duplicate `decision_key` rejection, retry snapshot reuse и legacy payload rejection.
- [ ] 4.2 Добавить frontend tests на новый slot-oriented `Topology Editor`, analyst-friendly `Bindings`, explicit binding-context coverage diagnostics и отсутствие inline legacy authoring.
- [ ] 4.3 Обновить API/contract tests для slot-based preview/read-model shape.
- [ ] 4.4 Выполнить `openspec validate refactor-topology-document-policy-slots --strict --no-interactive`.
