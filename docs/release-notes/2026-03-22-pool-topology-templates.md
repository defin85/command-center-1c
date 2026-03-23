# Release Notes — 2026-03-22

## add-pool-topology-templates

### Что изменилось

- Появился dedicated reusable topology template workspace `/pools/topology-templates` для create/revise reusable topology templates.
- `/pools/topology-templates` стала canonical producer surface: `Create template` публикует новый reusable topology template c immutable initial revision, а `Publish new revision` создаёт следующую immutable revision для уже существующего template.
- `/pools/catalog` остаётся consumer/assembly surface для template-based topology instantiation: оператор выбирает `topology_template_revision`, назначает `slot_key -> organization_id`, а concrete graph materialize'ится в обычный pool snapshot.
- При handoff из `/pools/catalog` используйте `Return to pool topology`, чтобы вернуться в исходный `pool` и topology task context.
- Template edge defaults materialize'ятся в explicit `edge.metadata.document_policy_key`; preview/runtime не должны угадывать selector только по положению edge в graph.
- Existing read APIs для graph/snapshots продолжают возвращать concrete materialized topology без отдельного template-only read path.

### Operator actions

1. Для создания или ревизии reusable topology откройте `/pools/topology-templates`.
2. Используйте `Create template` для нового reusable topology template и `Publish new revision` для следующей immutable revision существующего template.
3. Если вы пришли из `/pools/catalog`, нажмите `Return to pool topology`, чтобы восстановить исходный `pool` и topology task context.
4. В `/pools/catalog` выберите `topology_template_revision`, затем назначьте организации во все обязательные slot-ы.
5. Проверьте explicit selector defaults/overrides на template edges и добейтесь зелёного slot coverage перед сохранением.
6. Manual node/edge editor используйте только как fallback/remediation path для нестандартной схемы.

### Rollout note

- Этот rollout не делает automatic conversion существующих manual `pool` в template mode.
- Если нужно перевести historical pool на reusable topology template, canonical path — destructive reset или явное пересоздание затронутого `pool`, затем authoring в `/pools/topology-templates` и новый template-based snapshot в `/pools/catalog`.
- Не ожидайте, что старые `pool` автоматически получат `topology_template_revision_id`, `slot_assignments` или template edge defaults как побочный эффект rollout.
