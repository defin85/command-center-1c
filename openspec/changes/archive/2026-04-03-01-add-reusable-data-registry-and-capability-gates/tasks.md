## 1. Registry Foundation
- [x] 1.1 Ввести backend-owned executable reusable-data registry/type-handler contract для текущих canonical entity types.
- [x] 1.2 Зафиксировать capability matrix минимум для token exposure, bootstrap import, sync enqueue, outbox fan-out и direct binding.
- [x] 1.3 Подготовить generated registry artifact/schema для `contracts/**` и frontend consumption.

## 2. Runtime Gating
- [x] 2.1 Перевести token parsing и token catalog selection на registry-driven resolution.
- [x] 2.2 Перевести bootstrap entity eligibility и dependency ordering на registry-driven checks.
- [x] 2.3 Перевести sync/outbox routing на explicit capability gates с default-deny semantics.
- [x] 2.4 Оставить существующие enum/switch seams только как compatibility wrappers поверх registry.

## 3. Verification
- [x] 3.1 Добавить backend tests на registry resolution и default-deny capability behavior.
- [x] 3.2 Добавить contract/frontend tests, что generated registry artifact используется вместо handwritten duplicated lists.
- [x] 3.3 Прогнать `openspec validate 01-add-reusable-data-registry-and-capability-gates --strict --no-interactive`.
