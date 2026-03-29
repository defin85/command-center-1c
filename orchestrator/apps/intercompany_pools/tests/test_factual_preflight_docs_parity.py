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
    domain_map = _read_repo_doc("docs", "agent", "DOMAIN_MAP.md")
    spa_guide = _read_repo_doc("docs", "OPERATORS_SPA_GUIDE.md")

    expected_command = "preflight_pool_factual_sync"

    assert expected_command in runbook
    assert "--database-id <pilot-db-uuid>" in runbook
    assert "--strict" in runbook
    assert "/pools/factual?pool=<pool-uuid>&quarter_start=2026-01-01&focus=settlement&detail=1" in runbook
    assert "Create canonical batch" in runbook
    assert "quarter_start" in runbook

    assert expected_command in verify
    assert "apps/intercompany_pools/tests/test_factual_preflight.py" in verify
    assert "apps/intercompany_pools/tests/test_factual_preflight_command.py" in verify
    assert "apps/intercompany_pools/tests/test_factual_preflight_docs_parity.py" in verify
    assert "/pools/factual" in verify
    assert "Create canonical batch" in verify

    assert expected_command in debug
    assert "pilot/preflight evidence" in debug
    assert "/pools/factual" in debug
    assert "quarter_start" in debug

    assert "/pools/factual" in domain_map
    assert "/pools/factual" in spa_guide
    assert "Create canonical batch" in spa_guide
    assert "quarter_start" in spa_guide
