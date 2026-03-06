from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.databases.models import Database, InfobaseUserMapping
from apps.databases.odata import (
    ODataDocumentAdapter,
    ODataDocumentTransportError,
    resolve_database_odata_verify_tls,
)

from .document_completeness import collect_document_payload_mismatches
from .publication_auth_mapping import (
    ERROR_CODE_ODATA_MAPPING_AMBIGUOUS,
    ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
)


POOL_RUNTIME_VERIFICATION_CONTEXT_KEY = "pool_runtime_verification"
VERIFICATION_STATUS_NOT_VERIFIED = "not_verified"
VERIFICATION_STATUS_PASSED = "passed"
VERIFICATION_STATUS_FAILED = "failed"
POOL_PUBLICATION_VERIFICATION_FETCH_FAILED = "POOL_PUBLICATION_VERIFICATION_FETCH_FAILED"


def verify_published_documents(
    *,
    tenant_id: str,
    document_plan_artifact: Mapping[str, Any] | None,
    publication_results: list[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    expected_documents = _collect_expected_documents(document_plan_artifact=document_plan_artifact)
    successful_refs = _collect_successful_document_refs(publication_results=publication_results)
    if not expected_documents or not successful_refs:
        return {
            "status": VERIFICATION_STATUS_NOT_VERIFIED,
            "summary": None,
        }

    mismatches: list[dict[str, Any]] = []
    checked_targets: set[str] = set()
    verified_documents = 0

    for database_id, refs_by_document_key in successful_refs.items():
        expected_by_document_key = expected_documents.get(database_id)
        if not expected_by_document_key:
            continue

        database = Database.objects.filter(id=database_id, tenant_id=tenant_id).first()
        if database is None:
            mismatches.append(
                {
                    "database_id": database_id,
                    "entity_name": "",
                    "document_idempotency_key": "",
                    "field_or_table_path": "$database",
                    "kind": "database_not_found",
                }
            )
            continue

        try:
            username, password = _resolve_verification_credentials(database=database)
        except ValueError as exc:
            mismatches.append(
                {
                    "database_id": database_id,
                    "entity_name": "",
                    "document_idempotency_key": "",
                    "field_or_table_path": "$credentials",
                    "kind": str(exc),
                }
            )
            continue

        for document_key, document_ref in refs_by_document_key.items():
            expected = expected_by_document_key.get(document_key)
            if not expected:
                continue
            completeness_requirements = expected.get("completeness_requirements")
            if not isinstance(completeness_requirements, Mapping):
                continue

            entity_name = str(expected.get("entity_name") or "").strip()
            checked_targets.add(database_id)
            verified_documents += 1

            try:
                payload = _fetch_document_payload(
                    database=database,
                    username=username,
                    password=password,
                    entity_name=entity_name,
                    document_ref=str(document_ref or "").strip(),
                    expand_table_parts=list(
                        dict(completeness_requirements.get("required_table_parts") or {}).keys()
                    ),
                )
            except ValueError as exc:
                mismatches.append(
                    {
                        "database_id": database_id,
                        "entity_name": entity_name,
                        "document_idempotency_key": document_key,
                        "field_or_table_path": "$document",
                        "kind": str(exc),
                    }
                )
                continue

            mismatches.extend(
                collect_document_payload_mismatches(
                    database_id=database_id,
                    entity_name=entity_name,
                    document_idempotency_key=document_key,
                    payload=payload,
                    completeness_requirements=completeness_requirements,
                )
            )

    if verified_documents == 0:
        return {
            "status": VERIFICATION_STATUS_NOT_VERIFIED,
            "summary": None,
        }

    return {
        "status": VERIFICATION_STATUS_FAILED if mismatches else VERIFICATION_STATUS_PASSED,
        "summary": {
            "checked_targets": len(checked_targets),
            "verified_documents": verified_documents,
            "mismatches_count": len(mismatches),
            "mismatches": mismatches,
        },
    }


def _collect_expected_documents(*, document_plan_artifact: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(document_plan_artifact, Mapping):
        return {}
    raw_targets = document_plan_artifact.get("targets")
    if not isinstance(raw_targets, list):
        return {}

    expected_documents: dict[str, dict[str, Any]] = {}
    for target_raw in raw_targets:
        if not isinstance(target_raw, Mapping):
            continue
        database_id = str(target_raw.get("database_id") or "").strip()
        if not database_id:
            continue
        raw_chains = target_raw.get("chains")
        if not isinstance(raw_chains, list):
            continue
        database_documents = expected_documents.setdefault(database_id, {})
        for chain_raw in raw_chains:
            if not isinstance(chain_raw, Mapping):
                continue
            raw_documents = chain_raw.get("documents")
            if not isinstance(raw_documents, list):
                continue
            for document_raw in raw_documents:
                if not isinstance(document_raw, Mapping):
                    continue
                document_key = str(document_raw.get("idempotency_key") or "").strip()
                if not document_key:
                    continue
                database_documents[document_key] = {
                    "entity_name": str(document_raw.get("entity_name") or "").strip(),
                    "completeness_requirements": dict(
                        document_raw.get("completeness_requirements") or {}
                    )
                    if isinstance(document_raw.get("completeness_requirements"), Mapping)
                    else None,
                }
    return expected_documents


def _collect_successful_document_refs(
    *,
    publication_results: list[Mapping[str, Any]] | None,
) -> dict[str, dict[str, str]]:
    if not isinstance(publication_results, list):
        return {}
    refs_by_database: dict[str, dict[str, str]] = {}
    for result in publication_results:
        raw_attempts = result.get("attempts") if isinstance(result, Mapping) else None
        if not isinstance(raw_attempts, list):
            continue
        for attempt_raw in raw_attempts:
            if not isinstance(attempt_raw, Mapping):
                continue
            if str(attempt_raw.get("status") or "").strip().lower() != "success":
                continue
            database_id = str(
                attempt_raw.get("target_database")
                or attempt_raw.get("target_database_id")
                or ""
            ).strip()
            if not database_id:
                continue
            response_summary = attempt_raw.get("response_summary")
            if not isinstance(response_summary, Mapping):
                continue
            successful_document_refs = response_summary.get("successful_document_refs")
            if not isinstance(successful_document_refs, Mapping):
                continue
            database_refs = refs_by_database.setdefault(database_id, {})
            for raw_document_key, raw_document_ref in successful_document_refs.items():
                document_key = str(raw_document_key or "").strip()
                document_ref = str(raw_document_ref or "").strip()
                if document_key and document_ref:
                    database_refs[document_key] = document_ref
    return refs_by_database


def _resolve_verification_credentials(*, database: Database) -> tuple[str, str]:
    service_mappings = list(
        InfobaseUserMapping.objects.filter(
            database=database,
            is_service=True,
            user__isnull=True,
        ).only("ib_username", "ib_password", "id")[:2]
    )
    if len(service_mappings) > 1:
        raise ValueError(ERROR_CODE_ODATA_MAPPING_AMBIGUOUS)
    if len(service_mappings) != 1:
        raise ValueError(ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED)
    mapping = service_mappings[0]
    username = str(mapping.ib_username or "").strip()
    password = str(mapping.ib_password or "").strip()
    if not username or not password:
        raise ValueError(ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED)
    return username, password


def _fetch_document_payload(
    *,
    database: Database,
    username: str,
    password: str,
    entity_name: str,
    document_ref: str,
    expand_table_parts: list[str],
) -> dict[str, Any]:
    if not entity_name or not document_ref:
        raise ValueError(POOL_PUBLICATION_VERIFICATION_FETCH_FAILED)
    _ = expand_table_parts
    try:
        with ODataDocumentAdapter(
            base_url=str(database.odata_url or ""),
            username=username,
            password=password,
            timeout=database.connection_timeout,
            verify_tls=resolve_database_odata_verify_tls(database=database),
        ) as document_adapter:
            response = document_adapter.fetch_document(
                entity_name=entity_name,
                entity_id=_guid_literal(document_ref),
            )
    except ODataDocumentTransportError as exc:
        raise ValueError(POOL_PUBLICATION_VERIFICATION_FETCH_FAILED) from exc
    if response.status_code >= 400:
        raise ValueError(POOL_PUBLICATION_VERIFICATION_FETCH_FAILED)
    payload = response.json()
    return dict(payload) if isinstance(payload, Mapping) else {}


def _guid_literal(raw_document_ref: str) -> str:
    document_ref = str(raw_document_ref or "").strip()
    if document_ref.startswith("guid'") and document_ref.endswith("'"):
        return document_ref
    return f"guid'{document_ref}'"
