## 0. Prerequisites
- [ ] 0.1 Подтвердить, что `refactor-12-workflow-centric-analyst-modeling` принят как prerequisite platform phase.
- [ ] 0.2 Использовать authoring/runtime contracts из `refactor-12` без локального дублирования альтернативной process model в service domains.

## 1. Platform Contract
- [ ] 1.1 Определить канонический контракт `workflow-safe template`, включая metadata, validation и runtime expectations.
- [ ] 1.2 Определить канонический binding `service_action -> pinned workflow revision` и его lineage contract.

## 2. Workflow Integration
- [ ] 2.1 Расширить workflow authoring/runtime так, чтобы reusable service workflows могли состоять только из workflow-safe templates, decisions и subworkflows.
- [ ] 2.2 Зафиксировать observability и diagnostics от domain `service_action` до workflow execution и template steps.

## 3. Domain Surfaces
- [ ] 3.1 Спроектировать запуск curated service workflows из `/extensions` без показа raw workflow catalog.
- [ ] 3.2 Спроектировать аналогичный launch path для service operations в `/databases`/infobase user сценариях.
- [ ] 3.3 Сохранить direct execution path для одношаговых операций как явный compatibility mode.

## 4. Pilot Domains
- [ ] 4.1 Описать pilot onboarding для `extensions` service actions.
- [ ] 4.2 Описать pilot onboarding для `database.ib_user.*` service actions.

## 5. Validation
- [ ] 5.1 Обновить API/contracts/OpenAPI для workflow-safe templates и service action bindings.
- [ ] 5.2 Добавить automated tests для binding resolution, workflow-safe validation, domain launch flow и lineage diagnostics.
- [ ] 5.3 Провести `openspec validate add-13-service-workflow-automation --strict --no-interactive`.
