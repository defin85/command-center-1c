## 1. Canonical Binding Workspace
- [ ] 1.1 Зафиксировать публичный contract:
  - `GET /api/v2/pools/workflow-bindings/?pool_id=<uuid>` -> `{ pool_id, workflow_bindings[], collection_etag }`
  - `PUT /api/v2/pools/workflow-bindings/` -> request `{ pool_id, expected_collection_etag, workflow_bindings[] }`
  - `PUT /api/v2/pools/workflow-bindings/` -> response `{ pool_id, workflow_bindings[], collection_etag }`
  - stale token -> `409 application/problem+json` with `POOL_WORKFLOW_BINDING_COLLECTION_CONFLICT`
  - `expected_collection_etag` является единственным default workspace concurrency token
  - `POST /api/v2/pools/workflow-bindings/upsert/`, `GET/DELETE /api/v2/pools/workflow-bindings/{binding_id}/` остаются compatibility surface и не являются default workspace-save path
- [ ] 1.2 Реализовать backend transactional replace path поверх canonical binding store без partial apply и без возврата к metadata-backed source-of-truth.
- [ ] 1.3 Перевести default `/pools/catalog` binding workspace на canonical collection read/save path (`GET/PUT /api/v2/pools/workflow-bindings/`), убрать silent fallback к `pool.metadata["workflow_bindings"]` из shipped flow и ввести blocking remediation state для `canonical empty + legacy metadata present`.
- [ ] 1.4 Добавить backend/frontend coverage для сценариев `atomic replace success`, `stale collection conflict`, `no partial apply`, `PUT returns new collection_etag`, `legacy metadata enters blocking remediation state`.

## 2. Metadata Catalog Contract Source-of-Truth
- [ ] 2.1 Зафиксировать, что `/api/v2/pools/odata-metadata/catalog/` и `/refresh/` используют generated OpenAPI contract как единственный typed source-of-truth для shipped frontend path.
- [ ] 2.2 Перевести frontend consumer metadata catalog на generated client/models и убрать hand-written runtime DTO drift для shared snapshot markers.
- [ ] 2.3 Добавить parity gates/tests для цепочки `runtime serializer -> OpenAPI source -> generated client -> frontend consumer` по metadata catalog surface.

## 3. Rollout Evidence Contract
- [ ] 3.1 Зафиксировать стабильный capability artifact path `docs/observability/artifacts/workflow-hardening-rollout-evidence/` и опубликовать contract artifacts:
  - `workflow-hardening-cutover-evidence.schema.json`
  - `workflow-hardening-cutover-evidence.example.json`
  - `README.md` с verifier invocation и interpretation rules
  - default live bundle location `docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`
- [ ] 3.2 Зафиксировать bundle v1 contract:
  - top-level fields `schema_version`, `change_id`, `git_sha`, `environment`, `tenant_id`, `runbook_version`, `captured_at`, `bundle_digest`, `evidence_refs[]`, `overall_status`, `sign_off[]`
  - `environment in {staging, production}`
  - `overall_status in {go, no_go}`
  - `bundle_digest` / `evidence_refs[].digest` in format `sha256:<hex>`
  - `evidence_refs[].result in {passed, failed, not_applicable}`
  - required sign-off roles `{platform, security, operations}` with exactly one entry per role
  - machine-readable `migration_outcome` / `not_applicable reason`
- [ ] 3.3 Добавить verifier/gate semantics:
  - Django management command `verify_workflow_hardening_cutover_evidence`
  - input = bundle path/URI
  - output = `{ status, go_no_go, bundle_digest, missing_requirements[], failed_checks[] }`
  - exit code `0` only for `{ status=passed, go_no_go=go }`
  - fail-closed при отсутствии обязательных evidence refs, digest, sign-off или schema mismatch
- [ ] 3.4 Обновить runbook, release notes и cutover notes, чтобы они явно различали repository acceptance evidence и tenant live cutover evidence и ссылались на bundle artifact location + digest.

## 4. Validation
- [ ] 4.1 Обновить OpenAPI/contracts/generated clients под collection replace contract и metadata catalog parity requirements.
- [ ] 4.2 Добавить/обновить backend integration tests, frontend unit/browser tests и docs parity checks для нового hardening contract.
- [ ] 4.3 Провести `openspec validate tighten-workflow-hardening-canonical-contracts --strict --no-interactive`.
