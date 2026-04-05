from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.metadata_catalog import MetadataCatalogSnapshotResolution
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterGLAccountSetRevisionMember,
    PoolNodeVersion,
)
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


def _seed_factual_scope_bindings(
    *,
    pool: OrganizationPool,
    database: Database,
    quarter_start: date,
) -> dict[str, str]:
    from apps.intercompany_pools.factual_scope_selection import ensure_pool_factual_scope_selection

    selection = ensure_pool_factual_scope_selection(
        pool=pool,
        quarter_start=quarter_start,
    )
    members = list(
        PoolMasterGLAccountSetRevisionMember.objects.filter(
            revision_id=selection.gl_account_set_revision_id
        ).order_by("sort_order", "created_at")
    )
    account_refs: dict[str, str] = {}
    for member in members:
        ref_key = f"account-{str(member.gl_account_code).replace('.', '-')}"
        PoolMasterDataBinding.objects.create(
            tenant=pool.tenant,
            entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
            canonical_id=member.gl_account_canonical_id,
            database=database,
            ib_ref_key=ref_key,
            chart_identity=member.chart_identity,
        )
        account_refs[str(member.gl_account_code)] = ref_key
    return account_refs


@pytest.mark.django_db
def test_run_pool_factual_sync_preflight_reports_go_for_valid_surfaces_and_live_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.intercompany_pools.factual_preflight import run_pool_factual_sync_preflight

    _, pool, database = _create_pool_with_single_database()
    snapshot = _snapshot_for(database, _valid_metadata_payload())
    account_refs = _seed_factual_scope_bindings(
        pool=pool,
        database=database,
        quarter_start=date(2026, 1, 1),
    )
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
        if entity == "ChartOfAccounts_Хозрасчетный":
            return [
                {"Code": "62.01", "Ref_Key": "account-62"},
                {"Code": "90.01", "Ref_Key": "account-90"},
            ]
        if entity.startswith("AccountingRegister_Хозрасчетный/Turnovers("):
            return [{"Recorder_Key": "sale-1", "AmountTurnoverDt": "90.00"}]
        if entity == "InformationRegister_ДанныеПервичныхДокументов":
            return [{"Recorder_Key": "sale-1", "DocumentNumber": "123"}]
        return [{"Ref_Key": "sale-1"}]

    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._query_all_rows",
        _fake_query_all_rows,
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._probe_entity_rows",
        lambda **kwargs: [{"Ref_Key": "probe-info"}],
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_scope_selection._query_chart_ref_map",
        lambda **kwargs: {ref_key: code for code, ref_key in account_refs.items()},
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
    assert checks["gl_account_bindings"]["ok"] is True
    assert checks["bounded_scope"]["ok"] is True
    assert checks["live_probe"]["ok"] is True
    assert database_report["live_probe"]["boundary_reads"]["accounting_register"] == 1
    assert database_report["live_probe"]["boundary_reads"]["information_register"] == 1
    assert database_report["live_probe"]["boundary_reads"]["Document_РеализацияТоваровУслуг"] == 1
    assert database_report["live_probe"]["boundary_probes"]["accounting_register"] == {
        "entity": database_report["live_probe"]["accounting_register_entity"],
        "row_count": 1,
        "probe_ok": True,
    }
    assert database_report["live_probe"]["boundary_probes"]["information_register"] == {
        "entity": "InformationRegister_ДанныеПервичныхДокументов",
        "row_count": 1,
        "probe_ok": True,
    }
    assert database_report["live_probe"]["boundary_probes"]["Document_РеализацияТоваровУслуг"] == {
        "entity": "Document_РеализацияТоваровУслуг",
        "row_count": 1,
        "probe_ok": True,
    }
    assert "Turnovers(" in database_report["live_probe"]["accounting_register_entity"]
    assert "StartPeriod=datetime'2026-01-01T00:00:00'" in database_report["live_probe"]["accounting_register_entity"]
    assert "EndPeriod=datetime'2026-03-31T23:59:59'" in database_report["live_probe"]["accounting_register_entity"]
    assert "Condition='(Организация_Key eq guid''" in database_report["live_probe"]["accounting_register_entity"]
    assert "AccountCondition='Account_Key eq guid''account-62-01'' or Account_Key eq guid''account-90-01'''" in (
        database_report["live_probe"]["accounting_register_entity"]
    )
    assert database_report["live_probe"]["account_code_refs"] == {
        "62.01": "account-62-01",
        "90.01": "account-90-01",
    }


@pytest.mark.django_db
def test_run_pool_factual_sync_preflight_records_successful_accounting_probe_even_for_zero_row_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.intercompany_pools.factual_preflight import run_pool_factual_sync_preflight

    _, pool, database = _create_pool_with_single_database()
    snapshot = _snapshot_for(database, _valid_metadata_payload())
    account_refs = _seed_factual_scope_bindings(
        pool=pool,
        database=database,
        quarter_start=date(2026, 1, 1),
    )

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
        del database, filter_query, order_by
        if entity == "ChartOfAccounts_Хозрасчетный":
            return [
                {"Code": "62.01", "Ref_Key": "account-62"},
                {"Code": "90.01", "Ref_Key": "account-90"},
            ]
        if entity.startswith("AccountingRegister_Хозрасчетный/Turnovers("):
            return []
        return []

    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._query_all_rows",
        _fake_query_all_rows,
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._probe_entity_rows",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_scope_selection._query_chart_ref_map",
        lambda **kwargs: {ref_key: code for code, ref_key in account_refs.items()},
    )

    report = run_pool_factual_sync_preflight(
        pool_id=str(pool.id),
        quarter_start=date(2026, 1, 1),
        requested_by_username="pilot-user",
    )

    database_report = report["databases"][0]
    assert report["decision"] == "go"
    assert database_report["checks"][-1]["key"] == "live_probe"
    assert database_report["checks"][-1]["ok"] is True
    assert database_report["live_probe"]["boundary_reads"]["accounting_register"] == 0
    assert database_report["live_probe"]["boundary_probes"]["accounting_register"] == {
        "entity": database_report["live_probe"]["accounting_register_entity"],
        "row_count": 0,
        "probe_ok": True,
    }


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
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._probe_entity_rows",
        lambda **kwargs: [{"Ref_Key": "probe-info"}],
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
def test_run_pool_factual_sync_preflight_uses_live_metadata_when_shared_snapshot_is_drifted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.intercompany_pools.business_configuration_profile import BUSINESS_CONFIGURATION_PROFILE_KEY
    from apps.intercompany_pools.factual_preflight import run_pool_factual_sync_preflight

    _, pool, database = _create_pool_with_single_database()
    snapshot_payload = _valid_metadata_payload()
    snapshot_payload["information_registers"] = []
    snapshot = _snapshot_for(database, snapshot_payload)
    account_refs = _seed_factual_scope_bindings(
        pool=pool,
        database=database,
        quarter_start=date(2026, 1, 1),
    )
    database.metadata = {
        BUSINESS_CONFIGURATION_PROFILE_KEY: {
            "config_name": "Accounting",
            "config_version": "3.0",
            "observed_metadata_hash": "b" * 64,
            "canonical_metadata_hash": "a" * 64,
            "publication_drift": True,
        }
    }
    database.save(update_fields=["metadata", "updated_at"])

    query_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight.refresh_metadata_catalog_snapshot",
        lambda **_: snapshot,
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight.describe_metadata_catalog_snapshot_resolution",
        lambda **_: MetadataCatalogSnapshotResolution(
            resolution_mode="shared_scope",
            is_shared_snapshot=True,
            provenance_database_id="peer-database",
            provenance_confirmed_at=snapshot.fetched_at,
        ),
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._fetch_live_catalog_payload",
        lambda **_: _valid_metadata_payload(),
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
        if entity == "ChartOfAccounts_Хозрасчетный":
            return [
                {"Code": "62.01", "Ref_Key": "account-62"},
                {"Code": "90.01", "Ref_Key": "account-90"},
            ]
        if entity.startswith("AccountingRegister_Хозрасчетный/Turnovers("):
            return [{"Recorder_Key": "sale-1", "AmountTurnoverDt": "90.00"}]
        if entity == "InformationRegister_ДанныеПервичныхДокументов":
            return [{"Recorder_Key": "sale-1", "DocumentNumber": "123"}]
        return [{"Ref_Key": "sale-1"}]

    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._query_all_rows",
        _fake_query_all_rows,
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._probe_entity_rows",
        lambda **kwargs: [{"Ref_Key": "probe-info"}],
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_scope_selection._query_chart_ref_map",
        lambda **kwargs: {ref_key: code for code, ref_key in account_refs.items()},
    )

    report = run_pool_factual_sync_preflight(
        pool_id=str(pool.id),
        quarter_start=date(2026, 1, 1),
        requested_by_username="pilot-user",
    )

    assert report["decision"] == "go"
    database_report = report["databases"][0]
    checks = {item["key"]: item for item in database_report["checks"]}
    assert checks["published_boundary"]["ok"] is True
    assert checks["published_boundary"]["metadata_payload_source"] == "live_publication"
    assert checks["live_probe"]["ok"] is True
    assert query_calls


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


@pytest.mark.django_db
def test_run_pool_factual_sync_preflight_fails_closed_when_live_ref_key_resolves_to_wrong_gl_account_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.intercompany_pools.factual_preflight import run_pool_factual_sync_preflight
    from apps.intercompany_pools.factual_scope_selection import POOL_FACTUAL_SCOPE_LIVE_LOOKUP_FAILED

    _, pool, database = _create_pool_with_single_database()
    snapshot = _snapshot_for(database, _valid_metadata_payload())
    account_refs = _seed_factual_scope_bindings(
        pool=pool,
        database=database,
        quarter_start=date(2026, 1, 1),
    )

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
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_preflight._probe_entity_rows",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "apps.intercompany_pools.factual_scope_selection._query_chart_ref_map",
        lambda **kwargs: {
            account_refs["62.01"]: "90.01",
            account_refs["90.01"]: "90.01",
        },
    )

    report = run_pool_factual_sync_preflight(
        pool_id=str(pool.id),
        quarter_start=date(2026, 1, 1),
        requested_by_username="pilot-user",
    )

    assert report["decision"] == "no_go"
    database_report = report["databases"][0]
    checks = {item["key"]: item for item in database_report["checks"]}
    assert checks["gl_account_bindings"]["ok"] is False
    assert checks["gl_account_bindings"]["code"] == POOL_FACTUAL_SCOPE_LIVE_LOOKUP_FAILED
    blockers = checks["gl_account_bindings"]["blockers"]
    assert blockers[0]["kind"] == "gl_account_binding_stale"
    assert blockers[0]["diagnostic"]["gl_account_code"] == "62.01"
    assert blockers[0]["diagnostic"]["live_code"] == "90.01"
    assert checks["live_probe"]["ok"] is False
