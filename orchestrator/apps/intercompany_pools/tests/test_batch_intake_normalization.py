from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolBatchKind,
    PoolBatchSourceType,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.tenancy.models import Tenant


@pytest.fixture
def intake_scope() -> dict[str, object]:
    tenant = Tenant.objects.create(slug="batch-intake-normalization", name="Batch Intake Normalization")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code="batch-intake-normalization",
        name="Batch Intake Normalization",
    )
    return {
        "tenant": tenant,
        "pool": pool,
    }


@pytest.mark.django_db
def test_normalize_pool_batch_intake_builds_canonical_batch_from_schema_template_upload(
    intake_scope: dict[str, object],
) -> None:
    from apps.intercompany_pools.batch_intake_normalization import normalize_pool_batch_intake

    tenant = intake_scope["tenant"]
    pool = intake_scope["pool"]
    template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code="receipt-json-template",
        name="Receipt JSON Template",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        is_active=True,
        schema={
            "columns": {
                "organization_inn": "inn",
                "amount_with_vat": "amount",
                "external_id": "row_id",
            }
        },
    )

    result = normalize_pool_batch_intake(
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        schema_template=template,
        json_payload={
            "rows": [
                {"row_id": "r-001", "inn": "770100000001", "amount": "120.00"},
                {"row_id": "r-002", "inn": "770100000002", "amount": "30.50"},
            ]
        },
        raw_payload_ref="files/receipt-q1.json",
        source_reference="receipt-registry-q1",
        source_metadata={"upload_id": "upl-001"},
    )

    assert result.pool_id == str(pool.id)
    assert result.period_start == date(2026, 1, 1)
    assert result.period_end == date(2026, 3, 31)
    assert result.provenance.batch_kind == PoolBatchKind.RECEIPT
    assert result.provenance.source_type == PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD
    assert result.provenance.source_reference == "receipt-registry-q1"
    assert result.provenance.raw_payload_ref == "files/receipt-q1.json"
    assert result.provenance.schema_reference == {
        "template_id": str(template.id),
        "template_code": "receipt-json-template",
    }
    assert result.provenance.integration_reference is None
    assert result.provenance.source_metadata["upload_id"] == "upl-001"
    assert len(result.provenance.content_hash) == 64
    assert [line.organization_inn for line in result.lines] == ["770100000001", "770100000002"]
    assert [line.external_id for line in result.lines] == ["r-001", "r-002"]
    assert [line.amount_with_vat for line in result.lines] == [Decimal("120.00"), Decimal("30.50")]
    assert result.normalization_summary == {
        "processed_rows": 2,
        "normalized_rows": 2,
        "total_amount_with_vat": Decimal("150.50"),
    }


@pytest.mark.django_db
def test_normalize_pool_batch_intake_fails_closed_when_amount_mapping_is_missing(
    intake_scope: dict[str, object],
) -> None:
    from apps.intercompany_pools.batch_intake_normalization import normalize_pool_batch_intake

    tenant = intake_scope["tenant"]
    pool = intake_scope["pool"]
    template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code="missing-amount-template",
        name="Missing Amount Template",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        is_active=True,
        schema={"columns": {"organization_inn": "inn"}},
    )

    with pytest.raises(ValidationError, match="amount_with_vat"):
        normalize_pool_batch_intake(
            pool=pool,
            batch_kind=PoolBatchKind.RECEIPT,
            source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            schema_template=template,
            json_payload={"rows": [{"inn": "770100000001"}]},
        )


@pytest.mark.django_db
def test_normalize_pool_batch_intake_fails_closed_when_organization_value_is_missing(
    intake_scope: dict[str, object],
) -> None:
    from apps.intercompany_pools.batch_intake_normalization import normalize_pool_batch_intake

    tenant = intake_scope["tenant"]
    pool = intake_scope["pool"]
    template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code="missing-organization-value-template",
        name="Missing Organization Value Template",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        is_active=True,
        schema={"columns": {"organization_inn": "inn", "amount_with_vat": "amount"}},
    )

    with pytest.raises(ValidationError, match="organization_inn"):
        normalize_pool_batch_intake(
            pool=pool,
            batch_kind=PoolBatchKind.RECEIPT,
            source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            schema_template=template,
            json_payload={"rows": [{"inn": "", "amount": "120.00"}]},
        )


@pytest.mark.django_db
def test_normalize_pool_batch_intake_fails_closed_when_period_is_missing(
    intake_scope: dict[str, object],
) -> None:
    from apps.intercompany_pools.batch_intake_normalization import normalize_pool_batch_intake

    tenant = intake_scope["tenant"]
    pool = intake_scope["pool"]
    template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code="missing-period-template",
        name="Missing Period Template",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        is_active=True,
        schema={"columns": {"organization_inn": "inn", "amount_with_vat": "amount"}},
    )

    with pytest.raises(ValidationError, match="period_start"):
        normalize_pool_batch_intake(
            pool=pool,
            batch_kind=PoolBatchKind.RECEIPT,
            source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
            period_start=None,
            period_end=date(2026, 3, 31),
            schema_template=template,
            json_payload={"rows": [{"inn": "770100000001", "amount": "120.00"}]},
        )


@pytest.mark.django_db
def test_normalize_pool_batch_intake_uses_registered_integration_adapter(
    intake_scope: dict[str, object],
) -> None:
    from apps.intercompany_pools.batch_intake_normalization import (
        CanonicalPoolBatchLine,
        CanonicalPoolBatchNormalizationResult,
        CanonicalPoolBatchProvenance,
        register_pool_batch_intake_adapter,
        unregister_pool_batch_intake_adapter,
        normalize_pool_batch_intake,
    )

    pool = intake_scope["pool"]
    calls: list[dict[str, object]] = []

    def adapter(**kwargs):
        calls.append(kwargs)
        return CanonicalPoolBatchNormalizationResult(
            pool_id=str(pool.id),
            period_start=kwargs["period_start"],
            period_end=kwargs["period_end"],
            provenance=CanonicalPoolBatchProvenance(
                batch_kind=kwargs["batch_kind"],
                source_type=kwargs["source_type"],
                source_reference="integration-batch-q1",
                raw_payload_ref="integration://sales-report/q1",
                content_hash="f" * 64,
                source_metadata={"adapter": "test"},
                schema_reference=None,
                integration_reference={"adapter_code": "sales-report-http"},
            ),
            lines=[
                CanonicalPoolBatchLine(
                    line_no=1,
                    organization_inn="770100000010",
                    amount_with_vat=Decimal("42.00"),
                    external_id="sale-001",
                )
            ],
            normalization_summary={
                "processed_rows": 1,
                "normalized_rows": 1,
                "total_amount_with_vat": Decimal("42.00"),
            },
        )

    register_pool_batch_intake_adapter(PoolBatchSourceType.INTEGRATION, adapter)
    try:
        result = normalize_pool_batch_intake(
            pool=pool,
            batch_kind=PoolBatchKind.SALE,
            source_type=PoolBatchSourceType.INTEGRATION,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            integration_reference="sales-report-http",
            source_metadata={"request_id": "req-1"},
        )
    finally:
        unregister_pool_batch_intake_adapter(PoolBatchSourceType.INTEGRATION)

    assert len(calls) == 1
    assert calls[0]["integration_reference"] == "sales-report-http"
    assert result.provenance.integration_reference == {"adapter_code": "sales-report-http"}
    assert result.lines[0].amount_with_vat == Decimal("42.00")
