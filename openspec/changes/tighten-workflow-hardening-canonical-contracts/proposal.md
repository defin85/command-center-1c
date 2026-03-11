# Change: Ужесточить canonical contracts и rollout evidence для workflow-centric hardening

## Why
`add-refactor-14-workflow-centric-hardening` закрыл основной workflow-centric path, но после review остались три системных класса риска, которые не стоит чинить точечными bugfix'ами:
- default `/pools/catalog` binding workspace всё ещё допускает legacy fallback к `pool.metadata["workflow_bindings"]`, хотя canonical source-of-truth уже вынесен в dedicated binding store;
- сохранение нескольких bindings выполняется последовательностью `upsert/delete`, поэтому поздний conflict может дать partial apply вместо целостного результата workspace-save;
- checked-in repository acceptance evidence уже есть, но tenant-scoped live cutover proof остаётся шаблонным и не оформлен как формальный fail-closed go/no-go artifact.

Рядом с этим уже виден contract drift по `/api/v2/pools/odata-metadata/catalog*`: shipped frontend path использует hand-written DTO рядом с generated OpenAPI client, что создаёт второй источник истины для shared metadata snapshot contract.

## What Changes
- Зафиксировать, что default binding workspace, shipped read models и runtime path читают workflow bindings только из canonical binding collection и не используют silent fallback к `pool.metadata["workflow_bindings"]`.
- Добавить collection-level atomic replace contract для binding workspace на `/pools/catalog`, чтобы create/update/delete набора bindings выполнялись как одна conflict-safe операция без partial apply.
- Оставить single-binding CRUD как compatibility surface, но перевести default UI workspace на collection-safe path.
- Зафиксировать, что `/api/v2/pools/odata-metadata/catalog/` и `/refresh/` в shipped frontend path используют generated OpenAPI contract как единственный typed source-of-truth; hand-written DTO для этого surface не должны оставаться runtime-источником контракта.
- Ввести schema-validated tenant cutover evidence bundle и fail-closed go/no-go contract, который явно различает:
  - checked-in repository acceptance evidence для shipped default path;
  - tenant-scoped live cutover evidence для staging/prod rollout.
- Обновить runbook/release notes так, чтобы cutover ссылался на проверяемый evidence bundle и sign-off, а не только на repository-local proof.

## Impact
- Affected specs:
  - `pool-workflow-bindings`
  - `organization-pool-catalog`
  - `workflow-hardening-rollout-evidence`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/**`
  - `contracts/orchestrator/src/**`
  - `frontend/src/pages/Pools/**`
  - `frontend/src/api/**`
  - `frontend/src/api/generated/**`
  - `frontend/tests/**`
  - `docs/observability/**`
  - `docs/release-notes/**`

## Dependencies
- Change зависит от уже завершённого `add-refactor-14-workflow-centric-hardening` и не должен начинать новую redesign-ветку поверх workflow-centric model.
- Change желательно завершить до следующего крупного rollout, чтобы `add-13-service-workflow-automation` и последующие operator flows опирались на fully hardened binding/catalog/evidence contract.

## Breaking Changes
- **BREAKING (operational)**: staging/prod cutover workflow-centric hardening больше не должен считаться complete только по checked-in repository evidence; нужен отдельный tenant-scoped live evidence bundle с sign-off.
- **BREAKING (shipped UI contract)**: default `/pools/catalog` binding workspace перестаёт silently читать legacy `pool.metadata["workflow_bindings"]`; legacy payload остаётся только explicit import/backfill path.
- **BREAKING (workspace semantics)**: multi-binding save для default UI path становится atomic collection operation; partial apply перестаёт быть допустимой семантикой.

## Non-Goals
- Не менять продуктовую семантику lifecycle `/decisions`; gap вокруг отдельного `archive` action оформляется отдельно и не смешивается с этим hardening change.
- Не перепроектировать existing binding model, decision resources или shared metadata snapshots заново; change дожимает source-of-truth, save semantics и rollout proof.
- Не удалять сразу все per-binding endpoint'ы, если они нужны как compatibility surface для пошаговой миграции UI и интеграций.
