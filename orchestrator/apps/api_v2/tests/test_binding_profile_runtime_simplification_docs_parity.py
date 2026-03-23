from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_repo_doc(*parts: str) -> str:
    return (_repo_root().joinpath(*parts)).read_text(encoding="utf-8")


def test_runbook_documents_destructive_reset_for_missing_binding_profile_refs() -> None:
    runbook = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")

    assert "POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING" in runbook
    assert "не запускайте `backfill_pool_workflow_bindings`" in runbook
    assert "destructive reset" in runbook
    assert "/api/v2/pools/workflow-bindings/preview/" in runbook
    assert "`/pools/runs`" in runbook
    assert "`/pools/catalog`" in runbook


def test_binding_profile_runtime_simplification_release_note_documents_current_operator_path() -> None:
    release_note = _read_repo_doc(
        "docs",
        "release-notes",
        "2026-03-22-binding-profile-runtime-simplification.md",
    )

    assert "POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING" in release_note
    assert "не запускайте `backfill_pool_workflow_bindings`" in release_note
    assert "destructive reset" in release_note
    assert "/api/v2/pools/workflow-bindings/preview/" in release_note
    assert "/api/v2/pools/runs/" in release_note
    assert "/pools/execution-packs" in release_note
    assert "/pools/catalog" in release_note


def test_historical_hardening_release_note_marks_binding_profile_ref_backfill_as_superseded() -> None:
    release_note = _read_repo_doc(
        "docs",
        "release-notes",
        "2026-03-10-workflow-centric-hardening-cutover.md",
    )

    assert "Update 2026-03-22" in release_note
    assert "Не запускайте `backfill_pool_workflow_bindings`" in release_note
    assert "missing `binding_profile` refs" in release_note
    assert "2026-03-22-binding-profile-runtime-simplification.md" in release_note
