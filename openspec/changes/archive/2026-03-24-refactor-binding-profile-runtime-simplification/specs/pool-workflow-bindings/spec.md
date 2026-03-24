## ADDED Requirements

### Requirement: Attachment read model MUST оставаться derived projection pinned profile revision
Система ДОЛЖНА (SHALL) трактовать `binding_profile_revision_id` вместе с pool-local activation fields как единственный authoritative mutable state attachment-а в shipped path.

Operator-facing или runtime read-model МОЖЕТ (MAY) возвращать `resolved_profile` или эквивалентный convenience payload, но такая проекция:
- ДОЛЖНА (SHALL) выводиться из pinned `binding_profile_revision_id`;
- НЕ ДОЛЖНА (SHALL NOT) становиться второй primary mutable payload surface attachment-а;
- НЕ ДОЛЖНА (SHALL NOT) требовать повторной отправки reusable `workflow`, `decisions`, `parameters` или `role_mapping`, когда оператор меняет только pool-local activation fields.

Default mutate path для attachment-а ДОЛЖЕН (SHALL) принимать только pool-local activation fields и explicit repin на другой `binding_profile_revision_id`, если оператор осознанно меняет reusable схему.

#### Scenario: Pool-local mutate не требует повторной отправки reusable logic
- **GIVEN** attachment pinned на reusable `binding_profile_revision_id`
- **WHEN** оператор меняет только `status`, selector scope или effective period
- **THEN** shipped mutate contract принимает только pool-local fields и pinned profile reference
- **AND** authoritative `workflow`, `decisions`, `parameters` и `role_mapping` продолжают резолвиться из pinned profile revision

#### Scenario: Read model показывает derived resolved profile без второй mutable payload surface
- **GIVEN** attachment pinned на reusable `binding_profile_revision_id`
- **WHEN** оператор или runtime path читает attachment detail, collection или preview
- **THEN** response МОЖЕТ (MAY) включать `resolved_profile` как convenience summary
- **AND** этот payload derived из pinned profile revision, а не из отдельного attachment-local mutable source-of-truth

### Requirement: Default attachment reads MUST быть side-effect-free и не включать remediation/backfill compatibility path
Система ДОЛЖНА (SHALL) обеспечивать, что default shipped list/detail/preview/runtime path для attachment-ов не меняет canonical binding/profile state как implicit remediation.

Default shipped path НЕ ДОЛЖЕН (SHALL NOT):
- создавать generated `binding_profile` или `binding_profile_revision`;
- дописывать missing profile refs в canonical attachment row;
- silently чинить legacy residue как побочный эффект operator read или runtime resolution.

Если canonical attachment row не может быть корректно прочитан из-за отсутствующих или неразрешимых profile refs, shipped path ДОЛЖЕН (SHALL):
- fail-closed;
- вернуть blocking remediation state или machine-readable diagnostic.

Этот refactor НЕ ДОЛЖЕН (SHALL NOT) требовать shipped remediation/backfill compatibility flow для rows без resolvable profile refs; rollout допускает предварительное удаление или пересоздание затронутых historical данных вместо in-place repair.

#### Scenario: Missing profile refs не materialize'ятся молча на read path
- **GIVEN** canonical `pool_workflow_binding` существует, но не содержит корректных profile refs
- **WHEN** оператор открывает binding workspace, attachment detail или preview в shipped path
- **THEN** система возвращает blocking remediation или fail-closed diagnostic
- **AND** generated profile/revision не создаётся как побочный эффект этого чтения

#### Scenario: Legacy residue без profile refs остаётся fail-closed после rollout
- **GIVEN** historical `pool_workflow_binding` сохранился без resolvable profile refs после destructive rollout
- **WHEN** оператор или runtime path читает attachment detail, collection или preview
- **THEN** система возвращает blocking diagnostic
- **AND** не пытается materialize'ить generated profile/revision или repair canonical row
