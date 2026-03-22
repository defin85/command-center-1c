# Release Notes — 2026-03-22

## add-pool-topology-templates

### Что изменилось

- В API появился tenant-scoped reusable catalog `topology_template` / `topology_template_revision` для abstract slot graph без concrete `organization_id`.
- `/pools/catalog` теперь поддерживает template-based topology instantiation: оператор выбирает pinned `topology_template_revision_id`, назначает `slot_key -> organization_id`, а concrete graph materialize'ится в обычный pool snapshot.
- Template edge defaults materialize'ятся в explicit `edge.metadata.document_policy_key`; preview/runtime не должны угадывать selector только по положению edge в graph.
- Existing read APIs для graph/snapshots продолжают возвращать concrete materialized topology без отдельного template-only read path.

### Operator actions

1. Для типовых новых схем в `/pools/catalog` используйте `Topology Editor` -> `Template-based instantiation`.
2. Выберите published `topology_template_revision`, затем назначьте организации во все обязательные slot-ы.
3. Проверьте explicit selector defaults/overrides на template edges и добейтесь зелёного slot coverage перед сохранением.
4. Manual node/edge editor используйте только как fallback/remediation path для нестандартной схемы.

### Rollout note

- Этот rollout не делает automatic conversion существующих manual `pool` в template mode.
- Если нужно перевести historical pool на reusable topology template, canonical path — destructive reset или явное пересоздание затронутого `pool` с последующим новым template-based snapshot.
- Не ожидайте, что старые `pool` автоматически получат `topology_template_revision_id`, `slot_assignments` или template edge defaults как побочный эффект rollout.
