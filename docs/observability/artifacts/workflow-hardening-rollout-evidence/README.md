# Workflow hardening rollout evidence

Этот каталог хранит fail-closed contract для tenant-scoped live cutover evidence bundle.

Что лежит рядом:
- `workflow-hardening-cutover-evidence.schema.json` — schema для machine-readable bundle.
- `workflow-hardening-cutover-evidence.example.json` — валидный пример bundle v1.
- `live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json` — checked-in placeholder по стабильному artifact path.

Ключевое различие:
- `docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md` — checked-in repository acceptance evidence для shipped path внутри git.
- `docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json` — tenant live cutover artifact для staging/production gate.

`repository acceptance evidence не заменяет tenant live cutover evidence bundle`.

Verifier:
- `cd orchestrator && ../.venv/bin/python manage.py verify_workflow_hardening_cutover_evidence ../docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`
- `cd orchestrator && ../.venv/bin/python manage.py verify_workflow_hardening_cutover_evidence file:///home/egor/code/command-center-1c/docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`

Интерпретация verdict:
- `status=passed` означает, что bundle проходит schema/contract checks.
- `go_no_go=go` означает, что bundle не содержит blocking checks и может быть входом для tenant cutover gate.
- Команда завершится с кодом `0` только при `status=passed` и `go_no_go=go`.
- Любой `missing_requirements` или `failed_checks` приводит к fail-closed `no_go`.

Digest rule:
- bundle_digest рассчитывается по canonical JSON без top-level `bundle_digest`.
- Для canonical JSON используются `sort_keys=true` и separators `(",", ":")`.

Placeholder usage:
- Скопируй placeholder из `live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json` в tenant/environment path.
- Замени `tenant_id`, `git_sha`, sign-off actors и `evidence_refs[].uri`.
- Для `migration_outcome` разрешён `result=not_applicable`, но тогда обязателен machine-readable `reason`.
