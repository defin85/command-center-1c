from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .metadata_catalog import normalize_catalog_payload


ERROR_CODE_POOL_FACTUAL_SOURCE_PROFILE_INVALID = "POOL_FACTUAL_SOURCE_PROFILE_INVALID"

REQUIRED_FACTUAL_DOCUMENTS = (
    "Document_РеализацияТоваровУслуг",
    "Document_ВозвратТоваровОтПокупателя",
    "Document_КорректировкаРеализации",
)
REQUIRED_FACTUAL_INFORMATION_REGISTER = "InformationRegister_ДанныеПервичныхДокументов"
REQUIRED_FACTUAL_ACCOUNTING_REGISTER = "AccountingRegister_Хозрасчетный"
REQUIRED_FACTUAL_ACCOUNTING_FUNCTIONS = (
    "Balance",
    "Turnovers",
    "BalanceAndTurnovers",
)


def validate_factual_sync_source_profile(*, payload: Mapping[str, Any]) -> list[dict[str, str]]:
    normalized = normalize_catalog_payload(
        payload=dict(payload) if isinstance(payload, Mapping) else {}
    )

    documents_index = _index_entities(normalized.get("documents"))
    information_registers_index = _index_entities(normalized.get("information_registers"))
    accounting_registers_index = _index_entities(normalized.get("accounting_registers"))
    errors: list[dict[str, str]] = []

    for entity_name in REQUIRED_FACTUAL_DOCUMENTS:
        if entity_name not in documents_index:
            errors.append(
                {
                    "code": ERROR_CODE_POOL_FACTUAL_SOURCE_PROFILE_INVALID,
                    "path": f"documents.{entity_name}",
                    "detail": f"Required factual document '{entity_name}' is missing from published metadata.",
                }
            )

    if REQUIRED_FACTUAL_INFORMATION_REGISTER not in information_registers_index:
        errors.append(
            {
                "code": ERROR_CODE_POOL_FACTUAL_SOURCE_PROFILE_INVALID,
                "path": f"information_registers.{REQUIRED_FACTUAL_INFORMATION_REGISTER}",
                "detail": (
                    "Required information register "
                    f"'{REQUIRED_FACTUAL_INFORMATION_REGISTER}' is missing from published metadata."
                ),
            }
        )

    accounting_register = accounting_registers_index.get(REQUIRED_FACTUAL_ACCOUNTING_REGISTER)
    if accounting_register is None:
        errors.append(
            {
                "code": ERROR_CODE_POOL_FACTUAL_SOURCE_PROFILE_INVALID,
                "path": f"accounting_registers.{REQUIRED_FACTUAL_ACCOUNTING_REGISTER}",
                "detail": (
                    "Required accounting register "
                    f"'{REQUIRED_FACTUAL_ACCOUNTING_REGISTER}' is missing from published metadata."
                ),
            }
        )
        return errors

    function_names = {
        str(item.get("name") or "").strip()
        for item in (accounting_register.get("functions") or [])
        if isinstance(item, Mapping)
    }
    function_names.discard("")
    for function_name in REQUIRED_FACTUAL_ACCOUNTING_FUNCTIONS:
        if function_name not in function_names:
            errors.append(
                {
                    "code": ERROR_CODE_POOL_FACTUAL_SOURCE_PROFILE_INVALID,
                    "path": (
                        "accounting_registers."
                        f"{REQUIRED_FACTUAL_ACCOUNTING_REGISTER}.functions.{function_name}"
                    ),
                    "detail": (
                        "Accounting register "
                        f"'{REQUIRED_FACTUAL_ACCOUNTING_REGISTER}' is missing required bound function "
                        f"'{function_name}'."
                    ),
                }
            )

    return errors


def _index_entities(raw_entities: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_entities, list):
        return {}
    entities: dict[str, dict[str, Any]] = {}
    for raw_item in raw_entities:
        if not isinstance(raw_item, Mapping):
            continue
        entity_name = str(raw_item.get("entity_name") or "").strip()
        if entity_name:
            entities[entity_name] = dict(raw_item)
    return entities
