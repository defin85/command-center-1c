## 1. Spec
- [ ] 1.1 Добавить spec delta для `extensions-plan-apply`: ручной запуск из `/operations` использует тот же plan/apply pipeline.
- [ ] 1.2 Добавить spec delta для `extensions-action-catalog`: `/operations` manual entrypoint использует effective action catalog и preview provenance.

## 2. Frontend (/operations)
- [ ] 2.1 Добавить в New Operation Wizard тип ручной операции `extensions.set_flags` (fallback-mode).
- [ ] 2.2 Реализовать форму: `action_id`, `extension_name`, runtime flags input, `apply_mask`, reason (optional).
- [ ] 2.3 Добавить preview перед запуском (execution plan + binding provenance).
- [ ] 2.4 Подтверждённый запуск проводить через `POST /api/v2/extensions/plan/` -> `POST /api/v2/extensions/apply/`.
- [ ] 2.5 Обработать `DRIFT_CONFLICT` и re-plan/retry UX, как в `/extensions`.
- [ ] 2.6 Явно маркировать этот путь как fallback/ручной, а не основной bulk rollout.

## 3. Backend (при необходимости)
- [ ] 3.1 Убедиться, что `extensions.plan/apply` channel-agnostic для вызовов из `/operations`.
- [ ] 3.2 Закрыть найденные gaps в валидации/ошибках без добавления дублирующих execution endpoints.

## 4. Validation
- [ ] 4.1 `openspec validate add-operations-manual-extensions-set-flags-run --strict --no-interactive`
- [ ] 4.2 Релевантные frontend тесты wizard/manual flow (Vitest/Playwright).
- [ ] 4.3 Релевантные backend тесты `extensions plan/apply` для manual channel.
