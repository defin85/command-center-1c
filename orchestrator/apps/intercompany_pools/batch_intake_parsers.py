from __future__ import annotations

import json
import zipfile
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from typing import Any, Mapping
from xml.etree import ElementTree as ET

from django.core.exceptions import ValidationError

from .models import PoolSchemaTemplate, PoolSchemaTemplateFormat


def parse_pool_schema_template_rows(
    *,
    template: PoolSchemaTemplate,
    json_payload: Any | None = None,
    xlsx_bytes: bytes | None = None,
) -> list[dict[str, Any]]:
    if template.format == PoolSchemaTemplateFormat.JSON:
        return _parse_json_rows(json_payload)
    if template.format == PoolSchemaTemplateFormat.XLSX:
        if xlsx_bytes is None:
            raise ValidationError("XLSX template requires xlsx_bytes payload.")
        sheet_name = template.schema.get("sheet_name") if isinstance(template.schema, Mapping) else None
        return _parse_xlsx_rows(xlsx_bytes=xlsx_bytes, sheet_name=str(sheet_name) if sheet_name else None)
    raise ValidationError(f"Unsupported template format '{template.format}'.")


def parse_pool_schema_template_amount(
    raw: Any,
    *,
    quantizer: Decimal,
    field_name: str,
) -> Decimal:
    value = str(raw or "").strip().replace(",", ".")
    if not value:
        raise ValidationError(f"Missing {field_name} value")
    try:
        return Decimal(value).quantize(quantizer, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"Invalid {field_name} '{raw}'") from exc


def _parse_json_rows(payload: Any | None) -> list[dict[str, Any]]:
    if payload is None:
        raise ValidationError("JSON template requires json_payload.")

    value = payload
    if isinstance(payload, (str, bytes)):
        value = json.loads(payload)

    if isinstance(value, Mapping):
        rows = value.get("rows")
    else:
        rows = value
    if not isinstance(rows, list):
        raise ValidationError("JSON payload must be a list or an object with 'rows' list.")

    parsed: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            parsed.append(dict(row))
    return parsed


def _parse_xlsx_rows(*, xlsx_bytes: bytes, sheet_name: str | None) -> list[dict[str, Any]]:
    with zipfile.ZipFile(BytesIO(xlsx_bytes)) as archive:
        worksheet_path = _resolve_worksheet_path(archive=archive, sheet_name=sheet_name)
        shared_strings = _read_shared_strings(archive)
        root = ET.fromstring(archive.read(worksheet_path))
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rows = root.findall(".//x:sheetData/x:row", ns)

        matrix: list[dict[int, str]] = []
        for row in rows:
            values: dict[int, str] = {}
            for cell in row.findall("x:c", ns):
                ref = cell.attrib.get("r", "")
                column_idx = _column_index(ref)
                values[column_idx] = _cell_value(cell=cell, ns=ns, shared_strings=shared_strings)
            matrix.append(values)

    if not matrix:
        return []

    header_map = matrix[0]
    if not header_map:
        return []
    max_col = max(header_map.keys())
    headers = [header_map.get(idx, "").strip() for idx in range(max_col + 1)]

    parsed_rows: list[dict[str, Any]] = []
    for row_values in matrix[1:]:
        if not row_values:
            continue
        row_dict: dict[str, Any] = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            row_dict[header] = row_values.get(idx, "")
        if row_dict:
            parsed_rows.append(row_dict)
    return parsed_rows


def _resolve_worksheet_path(*, archive: zipfile.ZipFile, sheet_name: str | None) -> str:
    ns = {
        "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("rel:Relationship", ns)}

    target_rid = None
    sheet_nodes = workbook.findall(".//x:sheets/x:sheet", ns)
    if sheet_name:
        for sheet in sheet_nodes:
            if sheet.attrib.get("name") == sheet_name:
                target_rid = sheet.attrib.get(f"{{{ns['r']}}}id")
                break
    if target_rid is None and sheet_nodes:
        target_rid = sheet_nodes[0].attrib.get(f"{{{ns['r']}}}id")
    if target_rid is None:
        raise ValidationError("XLSX workbook has no sheets.")

    target = rel_map.get(target_rid)
    if not target:
        raise ValidationError("XLSX worksheet relationship is missing.")
    target = target.lstrip("/")
    if not target.startswith("xl/"):
        target = f"xl/{target}"
    return target


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return []

    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(archive.read(path))
    values: list[str] = []
    for node in root.findall(".//x:si", ns):
        text = "".join(node.itertext()).replace("\n", "").strip()
        values.append(text)
    return values


def _cell_value(*, cell: ET.Element, ns: dict[str, str], shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(cell.itertext()).replace("\n", "").strip()
    value_node = cell.find("x:v", ns)
    if value_node is None:
        return ""
    if cell_type == "s":
        idx_text = (value_node.text or "").strip()
        if idx_text.isdigit():
            idx = int(idx_text)
            if 0 <= idx < len(shared_strings):
                return shared_strings[idx]
    return (value_node.text or "").strip()


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    if not letters:
        return 0
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1
