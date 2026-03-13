from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

CHANGE_ID = "add-refactor-14-workflow-centric-hardening"
CHANGE_ARCHIVE_PATH = ("openspec", "changes", "archive", "2026-03-12-add-refactor-14-workflow-centric-hardening")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_repo_doc(*parts: str) -> str:
    return (_repo_root().joinpath(*parts)).read_text(encoding="utf-8")


def test_workflow_centric_runbook_documents_hardening_surfaces() -> None:
    runbook = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")

    assert "Decision lifecycle / migration: `/decisions`" in runbook
    assert "UI: `/decisions` -> `Import legacy edge`" in runbook
    assert "Import raw JSON" in runbook
    assert "compatibility shortcut: `/pools/catalog` -> `Import to /decisions`" in runbook
    assert "POST /api/v2/pools/odata-metadata/catalog/refresh/" in runbook
    assert "POST /api/v2/pools/<pool_id>/document-policy-migrations/" in runbook
    assert "canonical business-scoped snapshot" in runbook
    assert "pinned subworkflow" in runbook


def test_workflow_centric_hardening_cutover_notes_cover_backfill_and_rollback_window() -> None:
    cutover = _read_repo_doc(
        *CHANGE_ARCHIVE_PATH,
        "cutover.md",
    )

    assert "backfill_pool_workflow_bindings --dry-run --json" in cutover
    assert "/decisions` -> `Import legacy edge`" in cutover
    assert "Import raw JSON" in cutover
    assert "compatibility shortcut: `/pools/catalog` -> `Import to /decisions`" in cutover
    assert "POST /api/v2/pools/odata-metadata/catalog/refresh/" in cutover
    assert "POST /api/v2/pools/<pool_id>/document-policy-migrations/" in cutover
    assert "Следующий run должен стартовать только через явный `pool_workflow_binding_id`." in cutover
    assert "Rollback window" in cutover
    assert "pinned subworkflow" in cutover
    assert (
        "docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/"
        "workflow-hardening-cutover-evidence.json"
    ) in cutover
    assert "verify_workflow_hardening_cutover_evidence" in cutover
    assert "bundle_digest" in cutover
    assert "repository acceptance evidence не заменяет tenant live cutover evidence bundle" in cutover
    assert "templates/examples are inputs only and are not sufficient for staging/prod go-no-go" in cutover


def test_workflow_centric_hardening_release_note_documents_operator_changes() -> None:
    release_note = _read_repo_doc(
        "docs",
        "release-notes",
        "2026-03-10-workflow-centric-hardening-cutover.md",
    )

    assert "/decisions становится primary surface" in release_note
    assert "UI: `/decisions` -> `Import legacy edge`" in release_note
    assert "Import raw JSON" in release_note
    assert "Compatibility UI shortcut: `/pools/catalog` -> `Import to /decisions`" in release_note
    assert "workflow executor templates remain available here only as a compatibility/integration path" in release_note
    assert "shared business-identity metadata snapshots" in release_note
    assert "POST /api/v2/pools/{pool_id}/document-policy-migrations/" in release_note
    assert "legacy edge document_policy editor" in release_note
    assert "pinned subworkflow" in release_note


def test_workflow_centric_docs_reference_checked_in_evidence_templates() -> None:
    runbook = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")
    cutover = _read_repo_doc(
        *CHANGE_ARCHIVE_PATH,
        "cutover.md",
    )
    release_note = _read_repo_doc(
        "docs",
        "release-notes",
        "2026-03-10-workflow-centric-hardening-cutover.md",
    )

    expected_paths = [
        "docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md",
        "docs/observability/artifacts/refactor-14/shared-metadata-evidence.template.json",
        "docs/observability/artifacts/refactor-14/legacy-document-policy-migration-evidence.template.json",
        "docs/observability/artifacts/refactor-14/operator-canary-evidence.template.json",
    ]

    for path in expected_paths:
        assert path in runbook
        assert path in cutover
        assert path in release_note
        assert _repo_root().joinpath(path).exists()


def test_workflow_centric_tasks_validate_active_change_id() -> None:
    tasks = _read_repo_doc(*CHANGE_ARCHIVE_PATH, "tasks.md")

    assert f"openspec validate {CHANGE_ID} --strict --no-interactive" in tasks


def test_workflow_centric_repository_acceptance_evidence_describes_default_shipped_path() -> None:
    repository_evidence = _read_repo_doc(
        "docs",
        "observability",
        "artifacts",
        "refactor-14",
        "repository-acceptance-evidence.md",
    )

    assert "checked-in repository acceptance evidence" in repository_evidence
    assert "/api/v2/pools/runs/" in repository_evidence
    assert "/api/v2/pools/workflow-bindings/preview/" in repository_evidence
    assert "/decisions" in repository_evidence
    assert "frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx" in repository_evidence
    assert "orchestrator/apps/api_v2/tests/test_workflows_binding_policy.py" in repository_evidence
    assert "frontend/src/components/workflow/__tests__/PropertyEditor.test.tsx" in repository_evidence
    assert "frontend/tests/browser/workflow-io-editor.spec.ts" in repository_evidence


def test_workflow_centric_runbook_documents_business_identity_reuse_contract() -> None:
    runbook = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")

    assert "одинаковая business identity `config_name + config_version` определяет reuse" in runbook
    assert "`metadata_hash`/`publication_drift` остаются diagnostics-only markers" in runbook
    assert "не приводит к silent reuse при diverged metadata surface" not in runbook
    assert "Не возвращай вручную старый snapshot и не форсируй reuse только по совпадению `config_name + config_version`" not in runbook


def test_canonical_openspec_specs_align_with_business_identity_contract() -> None:
    organization_spec = _read_repo_doc("openspec", "specs", "organization-pool-catalog", "spec.md")
    policy_spec = _read_repo_doc("openspec", "specs", "pool-document-policy", "spec.md")
    workflow_spec = _read_repo_doc("openspec", "specs", "workflow-decision-modeling", "spec.md")

    assert "Canonical metadata snapshot identity ДОЛЖНА (SHALL) включать только:" in organization_spec
    assert "различие published OData metadata surface НЕ ДОЛЖНО (SHALL NOT) создавать отдельную compatibility identity." in organization_spec
    assert "#### Scenario: Одинаковая business identity переиспользует snapshot при publication drift" in organization_spec
    assert "`extensions_fingerprint` или эквивалентный marker extensions/applicability state" not in organization_spec
    assert "normalized OData metadata payload у них совпадает" not in organization_spec

    assert "валидировать и preview'ить новый `document_policy` против canonical metadata snapshot" in policy_spec
    assert "Same-release compatibility и reuse canonical snapshot должны следовать active metadata contract `/decisions`" in policy_spec
    assert "#### Scenario: Policy builder переиспользует canonical snapshot для same-release target identity" in policy_spec
    assert "#### Scenario: Decision revision сохраняет metadata snapshot provenance" in policy_spec
    assert "Diverged metadata surface блокирует reuse в policy builder" not in policy_spec

    assert "resolved metadata snapshot provenance/compatibility markers" in workflow_spec
    assert "#### Scenario: Decision revision сохраняет auditable compatibility context" in workflow_spec
    assert "#### Scenario: Revision вне target compatible set доступна как source, но не как default pin candidate" in workflow_spec
    assert "#### Scenario: Аналитик создаёт новую revision под новый релиз ИБ из старой revision" in workflow_spec


def test_workflow_centric_evidence_templates_are_marked_as_examples_only() -> None:
    templates_readme = _read_repo_doc("docs", "observability", "artifacts", "refactor-14", "README.md")

    assert "templates/examples" in templates_readme
    assert "not production rollout evidence" in templates_readme

    template_paths = [
        "docs/observability/artifacts/refactor-14/shared-metadata-evidence.template.json",
        "docs/observability/artifacts/refactor-14/legacy-document-policy-migration-evidence.template.json",
        "docs/observability/artifacts/refactor-14/operator-canary-evidence.template.json",
    ]

    for path in template_paths:
        template = _read_repo_doc(*path.split("/"))
        assert "Template/example only." in template
        assert "<" in template


def test_workflow_hardening_docs_distinguish_repository_evidence_from_tenant_live_bundle() -> None:
    runbook = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")
    release_note = _read_repo_doc(
        "docs",
        "release-notes",
        "2026-03-10-workflow-centric-hardening-cutover.md",
    )
    cutover = _read_repo_doc(
        *CHANGE_ARCHIVE_PATH,
        "cutover.md",
    )

    expected_repository_evidence = (
        "docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md"
    )
    expected_live_bundle = (
        "docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/"
        "workflow-hardening-cutover-evidence.json"
    )

    assert expected_repository_evidence in runbook
    assert expected_repository_evidence in release_note
    assert expected_repository_evidence in cutover
    assert expected_live_bundle in runbook
    assert expected_live_bundle in release_note
    assert expected_live_bundle in cutover
    assert "repository acceptance evidence не заменяет tenant live cutover evidence bundle" in runbook
    assert "repository evidence alone is not a tenant go-no-go artifact" in release_note
    assert "repository acceptance evidence не заменяет tenant live cutover evidence bundle" in cutover
    assert "templates/examples are inputs only and are not sufficient for staging/prod go-no-go" in cutover
    assert "verify_workflow_hardening_cutover_evidence" in runbook
    assert "verify_workflow_hardening_cutover_evidence" in release_note
    assert "verify_workflow_hardening_cutover_evidence" in cutover
    assert "bundle_digest" in cutover


def test_workflow_hardening_rollout_evidence_artifacts_exist_and_example_matches_schema() -> None:
    artifact_root = _repo_root().joinpath(
        "docs",
        "observability",
        "artifacts",
        "workflow-hardening-rollout-evidence",
    )
    schema_path = artifact_root / "workflow-hardening-cutover-evidence.schema.json"
    example_path = artifact_root / "workflow-hardening-cutover-evidence.example.json"
    readme_path = artifact_root / "README.md"
    live_placeholder_path = artifact_root / "live" / "<tenant_id>" / "<environment>" / "workflow-hardening-cutover-evidence.json"

    assert schema_path.exists()
    assert example_path.exists()
    assert readme_path.exists()
    assert live_placeholder_path.exists()

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    example = json.loads(example_path.read_text(encoding="utf-8"))
    live_placeholder = json.loads(live_placeholder_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    assert list(validator.iter_errors(example)) == []
    assert list(validator.iter_errors(live_placeholder)) == []
    assert example["schema_version"] == "workflow_hardening_cutover_evidence.v1"
    assert live_placeholder["schema_version"] == "workflow_hardening_cutover_evidence.v1"
    assert [item["kind"] for item in example["evidence_refs"]] == [
        "binding_preview",
        "create_run",
        "inspect_lineage",
        "migration_outcome",
    ]
    assert [item["role"] for item in example["sign_off"]] == [
        "platform",
        "security",
        "operations",
    ]

    readme = readme_path.read_text(encoding="utf-8")
    assert "verify_workflow_hardening_cutover_evidence" in readme
    assert "bundle_digest рассчитывается по canonical JSON без top-level `bundle_digest`" in readme
    assert "repository acceptance evidence не заменяет tenant live cutover evidence bundle" in readme
