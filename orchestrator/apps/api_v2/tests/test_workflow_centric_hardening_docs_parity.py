from __future__ import annotations

from pathlib import Path

CHANGE_ID = "add-refactor-14-workflow-centric-hardening"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_repo_doc(*parts: str) -> str:
    return (_repo_root().joinpath(*parts)).read_text(encoding="utf-8")


def test_workflow_centric_runbook_documents_hardening_surfaces() -> None:
    runbook = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")

    assert "Decision lifecycle / migration: `/decisions`" in runbook
    assert "POST /api/v2/pools/odata-metadata/catalog/refresh/" in runbook
    assert "POST /api/v2/pools/<pool_id>/document-policy-migrations/" in runbook
    assert "shared configuration-scoped snapshot" in runbook
    assert "pinned subworkflow" in runbook


def test_workflow_centric_hardening_cutover_notes_cover_backfill_and_rollback_window() -> None:
    cutover = _read_repo_doc(
        "openspec",
        "changes",
        CHANGE_ID,
        "cutover.md",
    )

    assert "backfill_pool_workflow_bindings --dry-run --json" in cutover
    assert "POST /api/v2/pools/odata-metadata/catalog/refresh/" in cutover
    assert "POST /api/v2/pools/<pool_id>/document-policy-migrations/" in cutover
    assert "Следующий run должен стартовать только через явный `pool_workflow_binding_id`." in cutover
    assert "Rollback window" in cutover
    assert "pinned subworkflow" in cutover


def test_workflow_centric_hardening_release_note_documents_operator_changes() -> None:
    release_note = _read_repo_doc(
        "docs",
        "release-notes",
        "2026-03-10-workflow-centric-hardening-cutover.md",
    )

    assert "/decisions становится primary surface" in release_note
    assert "workflow executor templates remain available here only as a compatibility/integration path" in release_note
    assert "shared configuration-scoped metadata snapshots" in release_note
    assert "POST /api/v2/pools/{pool_id}/document-policy-migrations/" in release_note
    assert "legacy edge document_policy editor" in release_note
    assert "pinned subworkflow" in release_note


def test_workflow_centric_docs_reference_checked_in_evidence_templates() -> None:
    runbook = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")
    cutover = _read_repo_doc(
        "openspec",
        "changes",
        CHANGE_ID,
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
    tasks = _read_repo_doc("openspec", "changes", CHANGE_ID, "tasks.md")

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
