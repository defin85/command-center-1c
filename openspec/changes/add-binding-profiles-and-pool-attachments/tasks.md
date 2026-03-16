## 1. Модель и контракты

- [ ] 1.1 Зафиксировать в спеках новую reusable сущность `binding_profile` + immutable `binding_profile_revision` с opaque `binding_profile_revision_id` как единственным runtime pin.
- [ ] 1.2 Зафиксировать `pool_workflow_binding` как pool-scoped attachment к `binding_profile_revision_id` с сохранением explicit runtime identity `pool_workflow_binding_id`.
- [ ] 1.3 Зафиксировать MVP-ограничение: attachment не поддерживает local overrides для workflow/slots/parameters/role mapping.
- [ ] 1.4 Зафиксировать lifecycle semantics: `deactivate` блокирует новые attach/re-attach и новые revisions, но не ломает уже pinned attachment-ы; hard revoke вынести за пределы MVP.

## 2. Backend и API

- [ ] 2.1 Спроектировать canonical store/API для profile catalog: list/detail/create/revise/deactivate на отдельном surface `/api/v2/pools/binding-profiles/*`.
- [ ] 2.2 Спроектировать attachment read/write contract для `/pools/catalog`, который ссылается на `binding_profile_revision_id`, а не дублирует full reusable payload.
- [ ] 2.3 Обновить preview/create-run/read-model contracts так, чтобы lineage содержал attachment provenance и pinned profile revision provenance.

## 3. Runtime

- [ ] 3.1 Спроектировать runtime resolution `pool_workflow_binding_id -> pool attachment -> binding_profile_revision -> effective runtime bundle`.
- [ ] 3.2 Зафиксировать fail-closed поведение для invalid/missing attachment reference и для attachment, выходящего за effective scope.
- [ ] 3.3 Зафиксировать новую формулу run idempotency fingerprint: `pool_workflow_binding_id` + `attachment revision` + `binding_profile_revision_id` + existing run inputs.

## 4. Frontend/operator surfaces

- [ ] 4.1 Спроектировать dedicated profile catalog UI на отдельном route `/pools/binding-profiles` как primary authoring surface для reusable схем.
- [ ] 4.2 Обновить `/pools/catalog` binding workspace до attachment-oriented UX: attach existing profile revision, редактирование только pool-local scope, handoff в profile catalog.
- [ ] 4.3 Обновить `/pools/runs` preview/create-run UX так, чтобы оператор выбирал attachment, а inspect показывал attachment + profile provenance.
- [ ] 4.4 Обновить `organization-pool-catalog` spec на attachment-oriented workspace без inline authoring reusable logic.

## 5. Migration и rollout

- [ ] 5.1 Зафиксировать conservative backfill: existing pool bindings materialize'ятся в generated one-off profiles без auto-deduplicate.
- [ ] 5.2 Зафиксировать rollout sequencing и зависимость от `refactor-topology-document-policy-slots`.

## 6. Проверка

- [ ] 6.1 Определить backend tests для profile revision immutability, attachment resolution, lineage snapshot и migration/backfill.
- [ ] 6.2 Определить frontend tests для profile catalog, attachment workspace и explicit runtime selection.
- [ ] 6.3 Определить contract/parity tests для новых profile/attachment surfaces.
- [ ] 6.4 Выполнить `openspec validate add-binding-profiles-and-pool-attachments --strict --no-interactive`.
