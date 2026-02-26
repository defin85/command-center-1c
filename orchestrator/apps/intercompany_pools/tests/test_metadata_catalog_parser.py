from __future__ import annotations

from apps.intercompany_pools.metadata_catalog import _parse_csdl_metadata


def test_parse_csdl_metadata_collects_fields_and_table_parts_from_base_types() -> None:
    xml_payload = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
  <edmx:DataServices>
    <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="StandardODATA">
      <EntityType Name="DocumentObject" Abstract="true">
        <Property Name="Ref_Key" Type="Edm.Guid" Nullable="false" />
        <Property Name="Number" Type="Edm.String" Nullable="false" />
        <NavigationProperty
          Name="CommonRows"
          Type="Collection(StandardODATA.Document_Sales_CommonRows_RowType)"
        />
      </EntityType>
      <EntityType Name="Document_Sales" BaseType="StandardODATA.DocumentObject">
        <Property Name="Amount" Type="Edm.Decimal" Nullable="false" />
        <NavigationProperty
          Name="Items"
          Type="Collection(StandardODATA.Document_Sales_Items_RowType)"
        />
      </EntityType>

      <EntityType Name="Document_Sales_CommonRows_RowType">
        <Property Name="BaseRowField" Type="Edm.String" Nullable="true" />
      </EntityType>
      <EntityType
        Name="Document_Sales_Items_RowType"
        BaseType="StandardODATA.Document_Sales_CommonRows_RowType"
      >
        <Property Name="Qty" Type="Edm.Decimal" Nullable="false" />
      </EntityType>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
"""

    payload = _parse_csdl_metadata(xml_payload)

    documents = payload.get("documents")
    assert isinstance(documents, list)
    sales_document = next(item for item in documents if item["entity_name"] == "Document_Sales")

    field_names = [field["name"] for field in sales_document["fields"]]
    assert field_names == ["Amount", "Number", "Ref_Key"]

    table_parts_by_name = {item["name"]: item for item in sales_document["table_parts"]}
    assert set(table_parts_by_name.keys()) == {"CommonRows", "Items"}

    common_rows_fields = [field["name"] for field in table_parts_by_name["CommonRows"]["row_fields"]]
    assert common_rows_fields == ["BaseRowField"]

    items_fields = [field["name"] for field in table_parts_by_name["Items"]["row_fields"]]
    assert items_fields == ["BaseRowField", "Qty"]
