from datetime import date

from apps.intercompany_pools.external_identity import (
    ExternalIdentityContext,
    build_external_run_key,
    resolve_external_document_identity,
)


def test_resolve_external_identity_prefers_guid_from_odata() -> None:
    context = ExternalIdentityContext(
        run_id="run-1",
        target_database_id="db-1",
        document_kind="sales_distribution",
        period_start=date(2026, 1, 1),
    )
    identity = resolve_external_document_identity(
        odata_payload={"Ref_Key": "550e8400-e29b-41d4-a716-446655440000"},
        context=context,
    )

    assert identity.strategy == "guid_from_odata"
    assert identity.value == "550e8400-e29b-41d4-a716-446655440000"


def test_resolve_external_identity_uses_fallback_when_guid_missing() -> None:
    context = ExternalIdentityContext(
        run_id="run-2",
        target_database_id="db-2",
        document_kind="sales_distribution",
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
    )
    identity = resolve_external_document_identity(
        odata_payload={"Number": "0001"},
        context=context,
    )

    assert identity.strategy == "external_run_key_fallback"
    assert identity.value.startswith("runkey-")
    assert len(identity.value) == len("runkey-") + 32


def test_external_run_key_is_deterministic() -> None:
    context = ExternalIdentityContext(
        run_id="run-3",
        target_database_id="db-3",
        document_kind="sales_distribution",
        period_start=date(2026, 3, 1),
    )
    key1 = build_external_run_key(context)
    key2 = build_external_run_key(context)

    assert key1 == key2
