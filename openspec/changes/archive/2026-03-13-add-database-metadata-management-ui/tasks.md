## 1. Databases management surface
- [x] 1.1 Зафиксировать canonical `/databases` UI surface для configuration profile и metadata snapshot выбранной ИБ.
- [x] 1.2 Описать обязательные read-only markers и statuses для business identity, verification state, snapshot state и publication drift.
- [x] 1.3 Зафиксировать два разных mutate action: `Re-verify configuration identity` и `Refresh metadata snapshot`, включая expected user feedback и handoff в operations там, где path асинхронный.

## 2. Consumer surface handoff
- [x] 2.1 Обновить spec `organization-pool-catalog`, чтобы `/pools/catalog` больше не считался primary metadata maintenance surface и вместо этого показывал status + CTA в `/databases`.
- [x] 2.2 Обновить spec `workflow-decision-modeling`, чтобы `/decisions` оставался metadata-aware consumer surface и при отсутствии/устаревании context направлял пользователя в `/databases`.

## 3. Validation and rollout
- [x] 3.1 Зафиксировать минимальный набор frontend tests для `/databases`, `/pools/catalog` и `/decisions`, который доказывает новый handoff и отсутствие скрытого primary mutate UX.
- [x] 3.2 Зафиксировать, какие существующие docs/tooltips/operator messages должны быть обновлены при реализации change.
- [x] 3.3 Прогнать `openspec validate add-database-metadata-management-ui --strict --no-interactive`.
