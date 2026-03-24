from __future__ import annotations

from apps.intercompany_pools.top_down_execution_pack_alias_adoption import (
    build_top_down_realization_alias_policy,
    build_top_down_receipt_alias_policy,
)


def _build_policy() -> dict[str, object]:
    return {
        "version": "document_policy.v1",
        "chains": [
            {
                "chain_id": "sample",
                "documents": [
                    {
                        "document_id": "doc-1",
                        "entity_name": "Document_Sample",
                        "document_role": "base",
                        "invoice_mode": "optional",
                        "field_mapping": {
                            "Организация_Key": "legacy-org-guid",
                            "Контрагент_Key": "legacy-counterparty-guid",
                            "ДоговорКонтрагента_Key": "legacy-contract-guid",
                            "Номенклатура_Key": "master_data.item.packing-service.ref",
                        },
                        "table_parts_mapping": {
                            "Услуги": [
                                {
                                    "Контрагент_Key": "legacy-line-counterparty-guid",
                                    "ДоговорКонтрагента_Key": "legacy-line-contract-guid",
                                    "Номенклатура_Key": "master_data.item.packing-service.ref",
                                }
                            ]
                        },
                        "link_rules": {},
                    }
                ],
            }
        ],
    }


def test_build_top_down_realization_alias_policy_rewrites_header_and_line_item_participants() -> None:
    policy = build_top_down_realization_alias_policy(
        policy=_build_policy(),
        contract_canonical_id="osnovnoy",
    )
    document = policy["chains"][0]["documents"][0]

    assert document["field_mapping"]["Организация_Key"] == "master_data.party.edge.parent.organization.ref"
    assert document["field_mapping"]["Контрагент_Key"] == "master_data.party.edge.child.counterparty.ref"
    assert document["field_mapping"]["ДоговорКонтрагента_Key"] == "master_data.contract.osnovnoy.edge.child.ref"
    assert document["field_mapping"]["Номенклатура_Key"] == "master_data.item.packing-service.ref"
    assert document["table_parts_mapping"]["Услуги"][0]["Контрагент_Key"] == (
        "master_data.party.edge.child.counterparty.ref"
    )
    assert document["table_parts_mapping"]["Услуги"][0]["ДоговорКонтрагента_Key"] == (
        "master_data.contract.osnovnoy.edge.child.ref"
    )


def test_build_top_down_receipt_alias_policy_rewrites_header_and_line_item_participants() -> None:
    policy = build_top_down_receipt_alias_policy(
        policy=_build_policy(),
        contract_canonical_id="osnovnoy",
    )
    document = policy["chains"][0]["documents"][0]

    assert document["field_mapping"]["Организация_Key"] == "master_data.party.edge.child.organization.ref"
    assert document["field_mapping"]["Контрагент_Key"] == "master_data.party.edge.parent.counterparty.ref"
    assert document["field_mapping"]["ДоговорКонтрагента_Key"] == "master_data.contract.osnovnoy.edge.parent.ref"
    assert document["field_mapping"]["Номенклатура_Key"] == "master_data.item.packing-service.ref"
    assert document["table_parts_mapping"]["Услуги"][0]["Контрагент_Key"] == (
        "master_data.party.edge.parent.counterparty.ref"
    )
    assert document["table_parts_mapping"]["Услуги"][0]["ДоговорКонтрагента_Key"] == (
        "master_data.contract.osnovnoy.edge.parent.ref"
    )
