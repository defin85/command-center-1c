## 1. Контракт reset capability
- [ ] 1.1 Зафиксировать spec для внутреннего tenant-scoped hard reset distribution-домена без публичного API.
- [ ] 1.2 Зафиксировать состав профиля `full_distribution_reset`: что удаляется и что обязано сохраниться.
- [ ] 1.3 Зафиксировать fail-closed preflight, explicit `dry-run` / `apply` и machine-readable итоговый summary.
- [ ] 1.4 Зафиксировать, что cleanup workflow/operations хвоста вычисляется по `pool_run` lineage, а не по широкому `execution_consumer="pools"`.
- [ ] 1.5 Зафиксировать исключения для master-data: sync jobs, checkpoints/outbox/conflicts и system-managed master-data workflow template не входят в purge scope.

## 2. Backend implementation
- [ ] 2.1 Реализовать internal management command с explicit tenant selector и режимами `--dry-run` / `--apply`.
- [ ] 2.2 Реализовать preflight summary: counts по моделям и blocking diagnostics по активным run/execution/outbox записям.
- [ ] 2.3 Реализовать ordered cleanup для pool-owned артефактов: runs lineage -> runs -> bindings -> topology -> pools.
- [ ] 2.4 Реализовать cleanup reusable authoring catalog: binding profiles, analyst-facing decisions, analyst-facing workflows, schema templates.
- [ ] 2.5 Реализовать cleanup cross-app execution tail: `workflow_step_results`, `workflow_executions`, `workflow_enqueue_outbox`, root `batch_operations` и их `tasks`, связанных именно с purge-кандидатами distribution-domain.
- [ ] 2.6 Обеспечить идемпотентность повторного запуска на частично или полностью очищенном tenant state.

## 3. Проверки
- [ ] 3.1 Добавить tests на `dry-run` summary без мутаций.
- [ ] 3.2 Добавить tests на fail-closed abort при non-terminal `pool_runs` и связанных pending execution/outbox rows.
- [ ] 3.3 Добавить tests на сохранение `Organizations` и master-data артефактов.
- [ ] 3.4 Добавить tests на исключение master-data system-managed workflow template из workflow purge.
- [ ] 3.5 Добавить tests на идемпотентный повторный `apply`.

## 4. Документация и валидация
- [ ] 4.1 Описать operator-facing запуск команды, ограничения и риски destructive reset.
- [ ] 4.2 Прогнать `openspec validate add-distribution-domain-hard-reset --strict --no-interactive`.
