from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_repo_doc(*parts: str) -> str:
    return (_repo_root().joinpath(*parts)).read_text(encoding="utf-8")


def test_workflow_centric_runbook_references_existing_archived_cutover_plan() -> None:
    content = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")

    stale_link = (
        "/home/egor/code/command-center-1c/openspec/changes/"
        "refactor-12-workflow-centric-analyst-modeling/cutover.md"
    )
    archived_link = (
        "/home/egor/code/command-center-1c/openspec/changes/archive/"
        "2026-03-11-refactor-12-workflow-centric-analyst-modeling/cutover.md"
    )

    assert stale_link not in content
    assert archived_link in content
    assert Path(archived_link).exists()


def test_workflow_centric_runbook_and_cutover_notes_require_explicit_binding_reference() -> None:
    runbook_content = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")
    cutover_content = _read_repo_doc(
        "openspec",
        "changes",
        "archive",
        "2026-03-11-refactor-12-workflow-centric-analyst-modeling",
        "cutover.md",
    )

    assert "В `/pools/runs` стартуй run через явный `pool_workflow_binding_id`." in runbook_content
    assert "Следующий run должен стартовать только через явный `pool_workflow_binding_id`." in cutover_content
    assert "либо через единственный active binding" not in cutover_content
    assert "при необходимости запустить run с явным `pool_workflow_binding_id`." not in cutover_content


def test_pools_api_breaking_change_release_note_documents_fail_closed_binding_requirement() -> None:
    release_note = _read_repo_doc(
        "docs",
        "release-notes",
        "2026-02-15-pools-run-input-breaking-change.md",
    )

    assert "POST /api/v2/pools/workflow-bindings/preview/" in release_note
    assert "без `pool_workflow_binding_id` отклоняются fail-closed" in release_note
    assert "даже если по selector есть ровно один кандидат" in release_note
    assert "Selector matching допустим только для UI prefill/assistive hint до submit." in release_note
    assert "Смена `pool_workflow_binding_id` создаёт новый idempotency fingerprint." in release_note
