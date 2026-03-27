from __future__ import annotations

from apps.intercompany_pools.factual_source_profile import (
    ERROR_CODE_POOL_FACTUAL_SOURCE_PROFILE_INVALID,
    validate_factual_sync_source_profile,
)


def test_validate_factual_sync_source_profile_accepts_required_registers_functions_and_documents() -> None:
    errors = validate_factual_sync_source_profile(
        payload={
            "documents": [
                {"entity_name": "Document_РеализацияТоваровУслуг", "fields": [], "table_parts": []},
                {"entity_name": "Document_ВозвратТоваровОтПокупателя", "fields": [], "table_parts": []},
                {"entity_name": "Document_КорректировкаРеализации", "fields": [], "table_parts": []},
            ],
            "information_registers": [
                {"entity_name": "InformationRegister_ДанныеПервичныхДокументов", "fields": []}
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
    )

    assert errors == []


def test_validate_factual_sync_source_profile_reports_missing_bound_function() -> None:
    errors = validate_factual_sync_source_profile(
        payload={
            "documents": [
                {"entity_name": "Document_РеализацияТоваровУслуг", "fields": [], "table_parts": []},
                {"entity_name": "Document_ВозвратТоваровОтПокупателя", "fields": [], "table_parts": []},
                {"entity_name": "Document_КорректировкаРеализации", "fields": [], "table_parts": []},
            ],
            "information_registers": [
                {"entity_name": "InformationRegister_ДанныеПервичныхДокументов", "fields": []}
            ],
            "accounting_registers": [
                {
                    "entity_name": "AccountingRegister_Хозрасчетный",
                    "fields": [],
                    "functions": [
                        {"name": "Balance", "parameters": []},
                        {"name": "Turnovers", "parameters": []},
                    ],
                }
            ],
        }
    )

    assert errors == [
        {
            "code": ERROR_CODE_POOL_FACTUAL_SOURCE_PROFILE_INVALID,
            "path": "accounting_registers.AccountingRegister_Хозрасчетный.functions.BalanceAndTurnovers",
            "detail": (
                "Accounting register 'AccountingRegister_Хозрасчетный' is missing required "
                "bound function 'BalanceAndTurnovers'."
            ),
        }
    ]
