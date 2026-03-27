from __future__ import annotations

from apps.intercompany_pools.metadata_catalog import _parse_csdl_metadata, normalize_catalog_payload


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


def test_parse_csdl_metadata_supports_legacy_odata_v3_namespaces() -> None:
    xml_payload = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx" Version="1.0">
  <edmx:DataServices xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <Schema xmlns="http://schemas.microsoft.com/ado/2009/11/edm" Namespace="StandardODATA">
      <EntityType Name="Document_Sales">
        <Property Name="Amount" Type="Edm.Decimal" Nullable="false" />
        <NavigationProperty
          Name="Items"
          Type="Collection(StandardODATA.Document_Sales_Items_RowType)"
        />
      </EntityType>
      <EntityType Name="Document_Sales_Items_RowType">
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
    assert field_names == ["Amount"]

    table_parts_by_name = {item["name"]: item for item in sales_document["table_parts"]}
    assert set(table_parts_by_name.keys()) == {"Items"}
    row_fields = [field["name"] for field in table_parts_by_name["Items"]["row_fields"]]
    assert row_fields == ["Qty"]


def test_normalize_catalog_payload_populates_table_part_row_fields_from_companion_entity() -> None:
    normalized = normalize_catalog_payload(
        payload={
            "documents": [
                {
                    "entity_name": "Document_Sales",
                    "display_name": "Sales",
                    "fields": [{"name": "Amount", "type": "Edm.Decimal", "nullable": False}],
                    "table_parts": [
                        {
                            "name": "Items",
                            "row_fields": [],
                        }
                    ],
                },
                {
                    "entity_name": "Document_Sales_Items",
                    "display_name": "Sales Items",
                    "fields": [
                        {"name": "LineNumber", "type": "Edm.Int32", "nullable": False},
                        {"name": "Qty", "type": "Edm.Decimal", "nullable": False},
                    ],
                    "table_parts": [],
                },
            ]
        }
    )

    documents = normalized.get("documents")
    assert isinstance(documents, list)
    sales_document = next(item for item in documents if item["entity_name"] == "Document_Sales")
    table_parts_by_name = {item["name"]: item for item in sales_document["table_parts"]}
    items_row_fields = [field["name"] for field in table_parts_by_name["Items"]["row_fields"]]
    assert items_row_fields == ["LineNumber", "Qty"]


def test_parse_csdl_metadata_collects_published_registers_and_bound_functions() -> None:
    xml_payload = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
  <edmx:DataServices>
    <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="StandardODATA">
      <EntityType Name="AccountingRegister_Хозрасчетный">
        <Property Name="Recorder" Type="Edm.String" Nullable="false" />
      </EntityType>
      <EntityType Name="InformationRegister_ДанныеПервичныхДокументов">
        <Property Name="Документ" Type="Edm.String" Nullable="false" />
        <Property Name="Номер" Type="Edm.String" Nullable="true" />
      </EntityType>
      <EntityContainer Name="DefaultContainer">
        <EntitySet
          Name="AccountingRegister_Хозрасчетный"
          EntityType="StandardODATA.AccountingRegister_Хозрасчетный"
        />
        <EntitySet
          Name="InformationRegister_ДанныеПервичныхДокументов"
          EntityType="StandardODATA.InformationRegister_ДанныеПервичныхДокументов"
        />
        <FunctionImport
          Name="Balance"
          IsBindable="true"
          ReturnType="Collection(StandardODATA.AccountingRegister_Хозрасчетный_Balance)"
        >
          <Parameter
            Name="bindingParameter"
            Type="StandardODATA.AccountingRegister_Хозрасчетный"
          />
          <Parameter Name="Period" Type="Edm.DateTime" />
        </FunctionImport>
        <FunctionImport
          Name="Turnovers"
          IsBindable="true"
          ReturnType="Collection(StandardODATA.AccountingRegister_Хозрасчетный_Turnover)"
        >
          <Parameter
            Name="bindingParameter"
            Type="StandardODATA.AccountingRegister_Хозрасчетный"
          />
          <Parameter Name="StartPeriod" Type="Edm.DateTime" />
          <Parameter Name="EndPeriod" Type="Edm.DateTime" />
        </FunctionImport>
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
"""

    payload = _parse_csdl_metadata(xml_payload)

    accounting_registers = payload.get("accounting_registers")
    assert isinstance(accounting_registers, list)
    accounting_register = next(
        item for item in accounting_registers if item["entity_name"] == "AccountingRegister_Хозрасчетный"
    )
    assert [field["name"] for field in accounting_register["fields"]] == ["Recorder"]
    assert [item["name"] for item in accounting_register["functions"]] == ["Balance", "Turnovers"]
    assert accounting_register["functions"][0]["parameters"] == [
        {"name": "Period", "type": "Edm.DateTime"}
    ]

    information_registers = payload.get("information_registers")
    assert isinstance(information_registers, list)
    information_register = next(
        item
        for item in information_registers
        if item["entity_name"] == "InformationRegister_ДанныеПервичныхДокументов"
    )
    assert [field["name"] for field in information_register["fields"]] == ["Документ", "Номер"]
