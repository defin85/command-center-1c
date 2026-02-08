from __future__ import annotations

import pytest

from apps.templates.operation_catalog_service import normalize_executor_payload, resolve_definition


def test_normalize_executor_payload_sets_canonical_driver():
    kind, payload, errors = normalize_executor_payload(
        executor_kind="designer_cli",
        executor_payload={"kind": "designer_cli", "command_id": "cluster.list"},
    )

    assert errors == []
    assert kind == "designer_cli"
    assert payload["kind"] == "designer_cli"
    assert payload["driver"] == "cli"


def test_normalize_executor_payload_fails_closed_on_driver_mismatch():
    _kind, _payload, errors = normalize_executor_payload(
        executor_kind="ibcmd_cli",
        executor_payload={"kind": "ibcmd_cli", "driver": "cli", "command_id": "infobase.extension.list"},
    )

    assert errors
    assert any(item["code"] == "DRIVER_KIND_MISMATCH" for item in errors)


@pytest.mark.django_db
def test_resolve_definition_dedup_is_stable_without_redundant_driver():
    first, _ = resolve_definition(
        tenant_scope="global",
        executor_kind="ibcmd_cli",
        executor_payload={
            "kind": "ibcmd_cli",
            "driver": "ibcmd",
            "command_id": "infobase.extension.list",
            "params": {},
        },
        contract_version=1,
    )
    second, _ = resolve_definition(
        tenant_scope="global",
        executor_kind="ibcmd_cli",
        executor_payload={
            "kind": "ibcmd_cli",
            "command_id": "infobase.extension.list",
            "params": {},
        },
        contract_version=1,
    )

    assert first.id == second.id

