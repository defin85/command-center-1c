from __future__ import annotations

import pytest

from apps.intercompany_pools.factual_read_boundary import (
    BOUNDARY_KIND_HTTP_SERVICE,
    BOUNDARY_KIND_ODATA,
    ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID,
    build_default_factual_odata_read_boundary,
    build_factual_http_service_read_boundary,
    build_factual_odata_read_boundary,
    validate_factual_read_boundary,
)


def test_build_default_factual_odata_read_boundary_exposes_allowlist_only() -> None:
    boundary = build_default_factual_odata_read_boundary()

    assert boundary.boundary_kind == BOUNDARY_KIND_ODATA
    assert boundary.direct_db_access is False
    assert boundary.entity_allowlist == (
        "AccountingRegister_Хозрасчетный",
        "Document_ВозвратТоваровОтПокупателя",
        "Document_КорректировкаРеализации",
        "Document_РеализацияТоваровУслуг",
        "InformationRegister_ДанныеПервичныхДокументов",
    )
    assert boundary.function_allowlist == ("Balance", "BalanceAndTurnovers", "Turnovers")
    assert boundary.service_name == ""
    assert boundary.endpoint_path == ""


def test_build_factual_odata_read_boundary_rejects_missing_published_surface() -> None:
    with pytest.raises(ValueError, match=ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID):
        build_factual_odata_read_boundary(
            payload={
                "documents": [
                    {"entity_name": "Document_РеализацияТоваровУслуг", "fields": [], "table_parts": []},
                    {"entity_name": "Document_ВозвратТоваровОтПокупателя", "fields": [], "table_parts": []},
                ],
                "information_registers": [],
                "accounting_registers": [],
            }
        )


def test_build_factual_http_service_read_boundary_requires_explicit_contract() -> None:
    boundary = build_factual_http_service_read_boundary(
        service_name="PoolFactualSalesReadService",
        endpoint_path="/hs/ccpool/factual-sales",
        operation_name="sales_report_slice",
    )

    assert boundary.boundary_kind == BOUNDARY_KIND_HTTP_SERVICE
    assert boundary.direct_db_access is False
    assert boundary.service_name == "PoolFactualSalesReadService"
    assert boundary.endpoint_path == "/hs/ccpool/factual-sales"
    assert boundary.operation_name == "sales_report_slice"


def test_validate_factual_read_boundary_rejects_direct_db_access() -> None:
    with pytest.raises(ValueError, match=ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID):
        validate_factual_read_boundary(
            boundary_kind=BOUNDARY_KIND_ODATA,
            direct_db_access=True,
            entity_allowlist=("AccountingRegister_Хозрасчетный",),
            function_allowlist=("Turnovers",),
        )
