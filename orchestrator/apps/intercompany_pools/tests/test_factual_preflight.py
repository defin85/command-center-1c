from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.metadata_catalog import MetadataCatalogSnapshotResolution
from apps.intercompany_pools.models import Organization, OrganizationPool, PoolNodeVersion
from apps.tenancy.models import Tenant


def _create_pool_with_single_database() -> tuple[Tenant, OrganizationPool, Database]:
    tenant = Tenant.objects.create(
        slug=f"factual-preflight-{uuid4().hex[:8]}",
        name="Factual Preflight",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Factual Preflight Pool",
    )
    database = Database.objects.create(
        tenant=tenant,
        name=f"factual-preflight-db-{uuid4().hex[:8]}",
        host="localhost",
        odata_url="http://localhost/factual/odata/standard.odata",
        username="factual-user",
        password="factual-pass",
        metadata={},
    )
    root = Organization.objects.create(
        tenant=tenant,
        name=f"Root {uuid4().hex[:6]}",
        inn=f"77{uuid4().int % 10**10:010d}",
    )
    leaf = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Leaf {uuid4().hex[:6]}",
        inn=f"78{uuid4().int % 10**10:010d}",
    )
    PoolNodeVersion.objects.create(
        pool=pool,
        organization=root,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf,
        effective_from=date(2026, 1, 1),
    )
    return tenant, pool, database


def _valid_metadata_payload() -> dict[str, object]:
    return {
        "documents": [
            {"entity_name": "Document_РеализацияТоваровУслуг", "fields": [], "table_parts": []},
            {"entity_name": "Document_ВозвратТоваровОтПокупателя", "fields": [], "table_parts": []},
            {"entity_name": "Document_КорректировкаРеализации", "fields": [], "table_parts": []},
        ],
        "information_registers": [
            {"entity_name": "InformationRegister_ДанныеПервичныхДокументов", "fields": []},
        ],
        "accounting_registers": [
            {
                "entity_name": "AccountingRegister_Хозрасчетный",
                "fields": [],
                "functions": [
                    {"name": "Balance", "parameters": []},
                    {"name": "Turnovers", "parameters": []},
                    {"name": "BalanceAndTurnovers", "parameters": []},
                ],
            }
        ],
    }


def _snapshot_for(database: Database, payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        database_id=database.id,
        payload=payload,
        fetched_at=datetime(2026, 3, 28, 12, 0, tzinfo=dt_timezone.utc),
        source="live_refresh",
        catalog_version="v1",
        config_name="Accounting",
        config_version="3.0",
        extensions_fingerprint="",
        metadata_hash="a" * 64,
    )


@pytest.mark.django_db
def test_run_pool_factual_sync_preflight_reports_go_for_valid_surfaces_and_live_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.intercompany_pools.factual_preflight import run_pool_factual_sync_preflight

    _, pool, database = _create_pool_with_single_database()
    snapshot = _snapshot_for(database, _valid_metadata_payload())
    query_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight.refresh_metadata_catalog_snapshot",
        lambda **_: snapshot,
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight.describe_metadata_catalog_snapshot_resolution",
        lambda **_: MetadataCatalogSnapshotResolution(
            resolution_mode="database_scope",
            is_shared_snapshot=False,
            provenance_database_id=str(database.id),
            provenance_confirmed_at=snapshot.fetched_at,
        ),
    )

    def _fake_query_all_rows(*, database, entity: str, filter_query: str | None, order_by: str | None):
        query_calls.append(
            {
                "database_id": str(database.id),
                "entity": entity,
                "filter_query": filter_query,
                "order_by": order_by,
            }
        )
        if entity.startswith("AccountingRegister_Хозрасчетный/Turnovers("):
            return [{"Recorder_Key": "sale-1", "AmountTurnoverDt": "90.00"}]
        if entity == "InformationRegister_ДанныеПервичныхДокументов":
            return [{"Recorder_Key": "sale-1", "DocumentNumber": "123"}]
        return [{"Ref_Key": "sale-1"}]

    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._query_all_rows",
        _fake_query_all_rows,
    )

    report = run_pool_factual_sync_preflight(
        pool_id=str(pool.id),
        quarter_start=date(2026, 1, 1),
        requested_by_username="pilot-user",
    )

    assert report["decision"] == "go"
    assert report["summary"]["database_count"] == 1
    database_report = report["databases"][0]
    checks = {item["key"]: item for item in database_report["checks"]}
    assert checks["source_availability"]["ok"] is True
    assert checks["published_metadata_refresh"]["ok"] is True
    assert checks["published_boundary"]["ok"] is True
    assert checks["bounded_scope"]["ok"] is True
    assert checks["live_probe"]["ok"] is True
    assert database_report["live_probe"]["boundary_reads"]["accounting_register"] == 1
    assert database_report["live_probe"]["boundary_reads"]["information_register"] == 1
    assert database_report["live_probe"]["boundary_reads"]["Document_РеализацияТоваровУслуг"] == 1
    assert "Turnovers(" in database_report["live_probe"]["accounting_register_entity"]
    assert any(
        call["entity"] == "Document_РеализацияТоваровУслуг"
        and "Organization_Key eq guid" in str(call["filter_query"])
        and "Date ge datetime'2026-01-01T00:00:00'" in str(call["filter_query"])
        for call in query_calls
    )


@pytest.mark.django_db
def test_run_pool_factual_sync_preflight_reports_no_go_when_required_surface_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.intercompany_pools.factual_preflight import run_pool_factual_sync_preflight

    _, pool, database = _create_pool_with_single_database()
    payload = _valid_metadata_payload()
    payload["information_registers"] = []
    snapshot = _snapshot_for(database, payload)
    query_calls: list[str] = []

    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight.refresh_metadata_catalog_snapshot",
        lambda **_: snapshot,
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight.describe_metadata_catalog_snapshot_resolution",
        lambda **_: MetadataCatalogSnapshotResolution(
            resolution_mode="database_scope",
            is_shared_snapshot=False,
            provenance_database_id=str(database.id),
            provenance_confirmed_at=snapshot.fetched_at,
        ),
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._query_all_rows",
        lambda **kwargs: query_calls.append(str(kwargs["entity"])) or [],
    )

    report = run_pool_factual_sync_preflight(
        pool_id=str(pool.id),
        quarter_start=date(2026, 1, 1),
        requested_by_username="pilot-user",
    )

    assert report["decision"] == "no_go"
    database_report = report["databases"][0]
    checks = {item["key"]: item for item in database_report["checks"]}
    assert checks["published_boundary"]["ok"] is False
    assert checks["live_probe"]["ok"] is False
    assert query_calls == []


@pytest.mark.django_db
def test_run_pool_factual_sync_preflight_reports_no_go_when_source_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.intercompany_pools.factual_preflight import run_pool_factual_sync_preflight

    _, pool, database = _create_pool_with_single_database()
    database.status = Database.STATUS_MAINTENANCE
    database.metadata = {"denied_message": "planned maintenance"}
    database.save(update_fields=["status", "metadata"])

    refresh_calls: list[str] = []
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight.refresh_metadata_catalog_snapshot",
        lambda **kwargs: refresh_calls.append(str(kwargs["database"].id)),
    )

    report = run_pool_factual_sync_preflight(
        pool_id=str(pool.id),
        quarter_start=date(2026, 1, 1),
        requested_by_username="pilot-user",
    )

    assert report["decision"] == "no_go"
    database_report = report["databases"][0]
    checks = {item["key"]: item for item in database_report["checks"]}
    assert checks["source_availability"]["ok"] is False
    assert checks["published_metadata_refresh"]["ok"] is False
    assert refresh_calls == []
