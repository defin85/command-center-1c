from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError

from apps.databases.models import Database
from apps.intercompany_pools.batch_intake_normalization import (
    CanonicalPoolBatchLine,
    CanonicalPoolBatchNormalizationResult,
    CanonicalPoolBatchProvenance,
)
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatchKind,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolNodeVersion,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sale-batch-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/sale-batch-{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.fixture
def sale_topology_scope() -> dict[str, object]:
    tenant = Tenant.objects.create(slug=f"sale-batch-{uuid4().hex[:6]}", name="Sale Batch Intake")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"sale-batch-pool-{uuid4().hex[:6]}",
        name="Sale Batch Intake",
    )
    root = Organization.objects.create(
        tenant=tenant,
        database=_create_database(tenant=tenant, suffix="root"),
        name="Root",
        inn="770300000001",
    )
    leaf_left = Organization.objects.create(
        tenant=tenant,
        database=_create_database(tenant=tenant, suffix="left"),
        name="Leaf Left",
        inn="770300000002",
    )
    leaf_right = Organization.objects.create(
        tenant=tenant,
        database=_create_database(tenant=tenant, suffix="right"),
        name="Leaf Right",
        inn="770300000003",
    )
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    leaf_left_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf_left,
        effective_from=date(2026, 1, 1),
    )
    leaf_right_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf_right,
        effective_from=date(2026, 1, 1),
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_left_node,
        effective_from=date(2026, 1, 1),
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_right_node,
        effective_from=date(2026, 1, 1),
    )
    return {
        "tenant": tenant,
        "pool": pool,
        "root": root,
        "leaf_left": leaf_left,
        "leaf_right": leaf_right,
    }


def _build_sale_batch(*, pool: OrganizationPool, lines: list[CanonicalPoolBatchLine]) -> CanonicalPoolBatchNormalizationResult:
    return CanonicalPoolBatchNormalizationResult(
        pool_id=str(pool.id),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        provenance=CanonicalPoolBatchProvenance(
            batch_kind=PoolBatchKind.SALE,
            source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
            source_reference="sales-q1",
            raw_payload_ref="files/sales-q1.json",
            content_hash="a" * 64,
            source_metadata={"upload_id": "upl-sale"},
            schema_reference={"template_id": str(uuid4()), "template_code": "sales-template"},
            integration_reference=None,
        ),
        lines=lines,
        normalization_summary={
            "processed_rows": len(lines),
            "normalized_rows": len(lines),
            "total_amount_with_vat": sum((line.amount_with_vat for line in lines), Decimal("0.00")),
        },
    )


@pytest.mark.django_db
def test_build_sale_batch_closing_contract_aggregates_lines_by_active_leaf(
    sale_topology_scope: dict[str, object],
) -> None:
    from apps.intercompany_pools.sale_batch_intake import build_sale_batch_closing_contract

    pool = sale_topology_scope["pool"]
    leaf_left = sale_topology_scope["leaf_left"]
    leaf_right = sale_topology_scope["leaf_right"]
    sale_batch = _build_sale_batch(
        pool=pool,
        lines=[
            CanonicalPoolBatchLine(
                line_no=1,
                organization_inn=leaf_left.inn,
                amount_with_vat=Decimal("30.00"),
                external_id="sale-001",
            ),
            CanonicalPoolBatchLine(
                line_no=2,
                organization_inn=leaf_left.inn,
                amount_with_vat=Decimal("20.00"),
                external_id="sale-002",
            ),
            CanonicalPoolBatchLine(
                line_no=3,
                organization_inn=leaf_right.inn,
                amount_with_vat=Decimal("15.50"),
                external_id="sale-003",
            ),
        ],
    )

    contract = build_sale_batch_closing_contract(pool=pool, normalized_batch=sale_batch)

    assert contract.pool_id == str(pool.id)
    assert contract.line_level_receipt_pairing_required is False
    assert contract.total_amount_with_vat == Decimal("65.50")
    assert [intent.organization_id for intent in contract.closing_intents] == [leaf_left.id, leaf_right.id]
    assert [intent.amount_with_vat for intent in contract.closing_intents] == [
        Decimal("50.00"),
        Decimal("15.50"),
    ]
    assert contract.closing_intents[0].source_line_nos == (1, 2)
    assert contract.closing_intents[0].source_external_ids == ("sale-001", "sale-002")
    assert contract.closing_intents[1].source_line_nos == (3,)


@pytest.mark.django_db
def test_build_sale_batch_closing_contract_rejects_non_leaf_targets(
    sale_topology_scope: dict[str, object],
) -> None:
    from apps.intercompany_pools.sale_batch_intake import build_sale_batch_closing_contract

    pool = sale_topology_scope["pool"]
    root = sale_topology_scope["root"]
    sale_batch = _build_sale_batch(
        pool=pool,
        lines=[
            CanonicalPoolBatchLine(
                line_no=1,
                organization_inn=root.inn,
                amount_with_vat=Decimal("12.00"),
                external_id="sale-root",
            )
        ],
    )

    with pytest.raises(ValidationError, match="active leaf publish target"):
        build_sale_batch_closing_contract(pool=pool, normalized_batch=sale_batch)


@pytest.mark.django_db
def test_build_sale_batch_closing_contract_rejects_non_sale_batch_kind(
    sale_topology_scope: dict[str, object],
) -> None:
    from apps.intercompany_pools.sale_batch_intake import build_sale_batch_closing_contract

    pool = sale_topology_scope["pool"]
    leaf_left = sale_topology_scope["leaf_left"]
    receipt_batch = CanonicalPoolBatchNormalizationResult(
        pool_id=str(pool.id),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        provenance=CanonicalPoolBatchProvenance(
            batch_kind=PoolBatchKind.RECEIPT,
            source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
            source_reference="receipt-q1",
            raw_payload_ref="files/receipt-q1.json",
            content_hash="b" * 64,
            source_metadata={},
            schema_reference={"template_id": str(uuid4()), "template_code": "receipt-template"},
            integration_reference=None,
        ),
        lines=[
            CanonicalPoolBatchLine(
                line_no=1,
                organization_inn=leaf_left.inn,
                amount_with_vat=Decimal("12.00"),
            )
        ],
        normalization_summary={
            "processed_rows": 1,
            "normalized_rows": 1,
            "total_amount_with_vat": Decimal("12.00"),
        },
    )

    with pytest.raises(ValidationError, match="sale"):
        build_sale_batch_closing_contract(pool=pool, normalized_batch=receipt_batch)
