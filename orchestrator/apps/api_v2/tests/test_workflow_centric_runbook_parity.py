from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def test_workflow_centric_runbook_references_existing_archived_cutover_plan() -> None:
    runbook_path = _repo_root() / "docs" / "observability" / "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md"
    content = runbook_path.read_text(encoding="utf-8")

    stale_link = (
        "/home/egor/code/command-center-1c/openspec/changes/"
        "refactor-12-workflow-centric-analyst-modeling/cutover.md"
    )
    archived_link = (
        "/home/egor/code/command-center-1c/openspec/changes/archive/"
        "2026-03-09-refactor-12-workflow-centric-analyst-modeling/cutover.md"
    )

    assert stale_link not in content
    assert archived_link in content
    assert Path(archived_link).exists()
