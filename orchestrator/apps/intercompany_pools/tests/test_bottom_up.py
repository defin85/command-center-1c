from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from django.core.exceptions import ValidationError

from apps.intercompany_pools.bottom_up import run_bottom_up_import
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.tenancy.models import Tenant


def _build_minimal_xlsx(*, rows: list[list[str]]) -> bytes:
    def _inline_cell(col: str, row: int, value: str) -> str:
        return f'<c r="{col}{row}" t="inlineStr"><is><t>{value}</t></is></c>'

    row_nodes: list[str] = []
    for row_idx, row in enumerate(rows, start=1):
        cells = []
        for col_idx, value in enumerate(row):
            col = chr(ord("A") + col_idx)
            cells.append(_inline_cell(col, row_idx, value))
        row_nodes.append(f'<row r="{row_idx}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        f'{"".join(row_nodes)}'
        "</sheetData>"
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
        "</sheets>"
        "</workbook>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


@pytest.fixture
def pool_graph() -> dict[str, object]:
    tenant = Tenant.objects.create(slug="pool-bottom-up", name="Pool Bottom Up")
    pool = OrganizationPool.objects.create(tenant=tenant, code="pool-bottom-up", name="Pool Bottom Up")
    root_org = Organization.objects.create(tenant=tenant, name="Root", inn="500000000001")
    left_org = Organization.objects.create(tenant=tenant, name="Left", inn="500000000002")
    right_org = Organization.objects.create(tenant=tenant, name="Right", inn="500000000003")
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    left_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=left_org,
        effective_from=date(2026, 1, 1),
    )
    right_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=right_org,
        effective_from=date(2026, 1, 1),
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=left_node,
        effective_from=date(2026, 1, 1),
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=right_node,
        effective_from=date(2026, 1, 1),
    )
    return {
        "tenant": tenant,
        "pool": pool,
        "left_inn": left_org.inn,
        "right_inn": right_org.inn,
    }


@pytest.mark.django_db
def test_bottom_up_json_import_balanced_report(pool_graph: dict[str, object]) -> None:
    tenant = pool_graph["tenant"]
    pool = pool_graph["pool"]
    template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code="json-public",
        name="JSON Public",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )

    result = run_bottom_up_import(
        pool=pool,
        template=template,
        period_date=date(2026, 1, 1),
        json_payload=[
            {"inn": pool_graph["left_inn"], "amount": "100.50"},
            {"inn": pool_graph["right_inn"], "amount": "49.50"},
        ],
    )

    assert result.summary.processed_rows == 2
    assert result.summary.accepted_rows == 2
    assert result.summary.diagnostics_count == 0
    assert result.summary.total_input_amount == Decimal("150.00")
    assert result.summary.total_root_amount == Decimal("150.00")
    assert result.summary.balance_delta == Decimal("0.00")
    assert result.summary.is_balanced is True
    assert [line.status for line in result.detailed_report] == ["accepted", "accepted"]


@pytest.mark.django_db
def test_bottom_up_import_marks_unknown_inn_without_stopping(pool_graph: dict[str, object]) -> None:
    tenant = pool_graph["tenant"]
    pool = pool_graph["pool"]
    template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code="json-public-unknown",
        name="JSON Public Unknown",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )

    result = run_bottom_up_import(
        pool=pool,
        template=template,
        period_date=date(2026, 1, 1),
        json_payload=[
            {"inn": "999999999999", "amount": "10.00"},
            {"inn": pool_graph["left_inn"], "amount": "20.00"},
        ],
    )

    assert result.summary.processed_rows == 2
    assert result.summary.accepted_rows == 1
    assert result.summary.total_input_amount == Decimal("20.00")
    assert result.summary.total_root_amount == Decimal("20.00")
    assert any(diag.code == "unknown_inn" for diag in result.diagnostics)
    assert result.detailed_report[0].status == "error"
    assert result.detailed_report[1].status == "accepted"


@pytest.mark.django_db
def test_bottom_up_xlsx_import_works_with_public_template(pool_graph: dict[str, object]) -> None:
    tenant = pool_graph["tenant"]
    pool = pool_graph["pool"]
    template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code="xlsx-public",
        name="XLSX Public",
        format=PoolSchemaTemplateFormat.XLSX,
        is_public=True,
        schema={"sheet_name": "Sheet1", "columns": {"inn": "inn", "amount": "amount"}},
    )
    payload = _build_minimal_xlsx(
        rows=[
            ["inn", "amount"],
            [str(pool_graph["left_inn"]), "70.00"],
            [str(pool_graph["right_inn"]), "30.00"],
        ]
    )

    result = run_bottom_up_import(
        pool=pool,
        template=template,
        period_date=date(2026, 1, 1),
        xlsx_bytes=payload,
    )

    assert result.summary.accepted_rows == 2
    assert result.summary.total_root_amount == Decimal("100.00")
    assert result.summary.is_balanced is True


@pytest.mark.django_db
def test_bottom_up_rejects_non_public_template(pool_graph: dict[str, object]) -> None:
    tenant = pool_graph["tenant"]
    pool = pool_graph["pool"]
    template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code="json-private",
        name="JSON Private",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=False,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )

    with pytest.raises(ValidationError, match="public templates"):
        run_bottom_up_import(
            pool=pool,
            template=template,
            period_date=date(2026, 1, 1),
            json_payload=[],
        )
