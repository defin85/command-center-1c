from __future__ import annotations

from pathlib import Path


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


def test_workflow_centric_hardening_cutover_notes_cover_backfill_and_rollback_window() -> None:
    cutover = _read_repo_doc(
        "openspec",
        "changes",
        "refactor-14-workflow-centric-hardening",
        "cutover.md",
    )

    assert "backfill_pool_workflow_bindings --dry-run --json" in cutover
    assert "POST /api/v2/pools/odata-metadata/catalog/refresh/" in cutover
    assert "POST /api/v2/pools/<pool_id>/document-policy-migrations/" in cutover
    assert "Следующий run должен стартовать только через явный `pool_workflow_binding_id`." in cutover
    assert "Rollback window" in cutover


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
