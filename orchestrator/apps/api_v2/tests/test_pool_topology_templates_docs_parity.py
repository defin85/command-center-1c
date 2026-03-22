from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_repo_doc(*parts: str) -> str:
    return (_repo_root().joinpath(*parts)).read_text(encoding="utf-8")


def test_runbook_documents_topology_template_catalog_and_destructive_adoption_path() -> None:
    runbook = _read_repo_doc("docs", "observability", "WORKFLOW_CENTRIC_POOLS_RUNBOOK.md")

    assert "GET /api/v2/pools/topology-templates/" in runbook
    assert "POST /api/v2/pools/topology-templates/" in runbook
    assert "template-based path" in runbook
    assert "Topology template rollout reset" in runbook
    assert "НЕ auto-convert existing manual pool graphs" in runbook
    assert "destructive reset" in runbook


def test_release_note_documents_template_based_instantiation_and_no_auto_conversion() -> None:
    release_note = _read_repo_doc(
        "docs",
        "release-notes",
        "2026-03-22-pool-topology-templates.md",
    )

    assert "topology_template" in release_note
    assert "topology_template_revision" in release_note
    assert "/pools/catalog" in release_note
    assert "Template-based instantiation" in release_note
    assert "automatic conversion" in release_note
    assert "destructive reset" in release_note
