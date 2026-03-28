from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_repo_doc(*parts: str) -> str:
    return (_repo_root().joinpath(*parts)).read_text(encoding="utf-8")


def test_factual_runbook_and_verify_document_live_preflight_command() -> None:
    runbook = _read_repo_doc("docs", "agent", "RUNBOOK.md")
    verify = _read_repo_doc("docs", "agent", "VERIFY.md")
    debug = _read_repo_doc("DEBUG.md")

    expected_command = "preflight_pool_factual_sync"

    assert expected_command in runbook
    assert "--database-id <pilot-db-uuid>" in runbook
    assert "--strict" in runbook

    assert expected_command in verify
    assert "apps/intercompany_pools/tests/test_factual_preflight.py" in verify
    assert "apps/intercompany_pools/tests/test_factual_preflight_command.py" in verify

    assert expected_command in debug
    assert "pilot/preflight evidence" in debug
