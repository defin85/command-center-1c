from __future__ import annotations

from typing import Any, Mapping


DOCUMENT_POLICY_VERSION = "document_policy.v1"
DOCUMENT_POLICY_METADATA_KEY = "document_policy"

POOL_DOCUMENT_POLICY_INVALID = "POOL_DOCUMENT_POLICY_INVALID"
POOL_DOCUMENT_POLICY_CHAIN_INVALID = "POOL_DOCUMENT_POLICY_CHAIN_INVALID"
POOL_DOCUMENT_POLICY_MAPPING_INVALID = "POOL_DOCUMENT_POLICY_MAPPING_INVALID"
POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE = "POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE"

DOCUMENT_POLICY_RESOLUTION_SOURCE_EDGE = "edge"
DOCUMENT_POLICY_RESOLUTION_SOURCE_POOL_DEFAULT = "pool_default"
DOCUMENT_POLICY_RESOLUTION_SOURCE_NONE = "none"

INVOICE_MODE_OPTIONAL = "optional"
INVOICE_MODE_REQUIRED = "required"
_ALLOWED_INVOICE_MODES = {
    INVOICE_MODE_OPTIONAL,
    INVOICE_MODE_REQUIRED,
}


def validate_document_policy_v1(*, policy: Any) -> dict[str, Any]:
    payload = _require_object(
        policy,
        field_name="document_policy",
        error_code=POOL_DOCUMENT_POLICY_INVALID,
    )
    version = _require_string(
        payload.get("version"),
        field_name="document_policy.version",
        error_code=POOL_DOCUMENT_POLICY_INVALID,
    )
    if version != DOCUMENT_POLICY_VERSION:
        raise ValueError(
            f"{POOL_DOCUMENT_POLICY_INVALID}: unsupported policy version '{version or '<empty>'}'"
        )

    chains_raw = payload.get("chains")
    if not isinstance(chains_raw, list) or not chains_raw:
        raise ValueError(
            f"{POOL_DOCUMENT_POLICY_CHAIN_INVALID}: document_policy.chains must be a non-empty array"
        )

    chains: list[dict[str, Any]] = []
    seen_chain_ids: set[str] = set()
    for chain_index, chain_raw in enumerate(chains_raw):
        chain_path = f"document_policy.chains[{chain_index}]"
        chain = _require_object(
            chain_raw,
            field_name=chain_path,
            error_code=POOL_DOCUMENT_POLICY_CHAIN_INVALID,
        )
        chain_id = _require_string(
            chain.get("chain_id"),
            field_name=f"{chain_path}.chain_id",
            error_code=POOL_DOCUMENT_POLICY_CHAIN_INVALID,
        )
        if chain_id in seen_chain_ids:
            raise ValueError(
                f"{POOL_DOCUMENT_POLICY_CHAIN_INVALID}: duplicate chain_id '{chain_id}' in document_policy.chains"
            )
        seen_chain_ids.add(chain_id)

        documents_raw = chain.get("documents")
        if not isinstance(documents_raw, list) or not documents_raw:
            raise ValueError(
                f"{POOL_DOCUMENT_POLICY_CHAIN_INVALID}: {chain_path}.documents must be a non-empty array"
            )

        documents: list[dict[str, Any]] = []
        seen_document_ids: set[str] = set()
        has_invoice_document = False
        requires_invoice = False
        for document_index, document_raw in enumerate(documents_raw):
            document_path = f"{chain_path}.documents[{document_index}]"
            document = _require_object(
                document_raw,
                field_name=document_path,
                error_code=POOL_DOCUMENT_POLICY_CHAIN_INVALID,
            )
            document_id = _require_string(
                document.get("document_id"),
                field_name=f"{document_path}.document_id",
                error_code=POOL_DOCUMENT_POLICY_CHAIN_INVALID,
            )
            if document_id in seen_document_ids:
                raise ValueError(
                    f"{POOL_DOCUMENT_POLICY_CHAIN_INVALID}: duplicate document_id '{document_id}' in {chain_path}.documents"
                )
            seen_document_ids.add(document_id)

            invoice_mode = str(document.get("invoice_mode") or INVOICE_MODE_OPTIONAL).strip().lower()
            if invoice_mode not in _ALLOWED_INVOICE_MODES:
                raise ValueError(
                    f"{POOL_DOCUMENT_POLICY_CHAIN_INVALID}: invalid invoice_mode '{invoice_mode or '<empty>'}' "
                    f"in {document_path}"
                )
            if invoice_mode == INVOICE_MODE_REQUIRED:
                requires_invoice = True

            document_role = _require_string(
                document.get("document_role"),
                field_name=f"{document_path}.document_role",
                error_code=POOL_DOCUMENT_POLICY_CHAIN_INVALID,
            )
            if document_role.lower() == "invoice":
                has_invoice_document = True

            normalized_document = {
                "document_id": document_id,
                "entity_name": _require_string(
                    document.get("entity_name"),
                    field_name=f"{document_path}.entity_name",
                    error_code=POOL_DOCUMENT_POLICY_CHAIN_INVALID,
                ),
                "document_role": document_role,
                "field_mapping": _require_object(
                    document.get("field_mapping"),
                    field_name=f"{document_path}.field_mapping",
                    error_code=POOL_DOCUMENT_POLICY_MAPPING_INVALID,
                    default_empty_object=True,
                ),
                "table_parts_mapping": _require_object(
                    document.get("table_parts_mapping"),
                    field_name=f"{document_path}.table_parts_mapping",
                    error_code=POOL_DOCUMENT_POLICY_MAPPING_INVALID,
                    default_empty_object=True,
                ),
                "link_rules": _require_object(
                    document.get("link_rules"),
                    field_name=f"{document_path}.link_rules",
                    error_code=POOL_DOCUMENT_POLICY_MAPPING_INVALID,
                    default_empty_object=True,
                ),
                "invoice_mode": invoice_mode,
            }
            link_to = document.get("link_to")
            if link_to is not None:
                normalized_document["link_to"] = _require_string(
                    link_to,
                    field_name=f"{document_path}.link_to",
                    error_code=POOL_DOCUMENT_POLICY_CHAIN_INVALID,
                )
            documents.append(normalized_document)

        if requires_invoice and not has_invoice_document:
            raise ValueError(
                f"{POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE}: {chain_path} requires invoice document"
            )

        normalized_chain: dict[str, Any] = {
            "chain_id": chain_id,
            "documents": documents,
        }
        chain_metadata = chain.get("metadata")
        if chain_metadata is not None:
            normalized_chain["metadata"] = _require_object(
                chain_metadata,
                field_name=f"{chain_path}.metadata",
                error_code=POOL_DOCUMENT_POLICY_CHAIN_INVALID,
            )
        chains.append(normalized_chain)

    normalized_policy: dict[str, Any] = {
        "version": DOCUMENT_POLICY_VERSION,
        "chains": chains,
    }
    policy_metadata = payload.get("metadata")
    if policy_metadata is not None:
        normalized_policy["metadata"] = _require_object(
            policy_metadata,
            field_name="document_policy.metadata",
            error_code=POOL_DOCUMENT_POLICY_INVALID,
        )
    return normalized_policy


def resolve_document_policy_from_edge_metadata(*, metadata: Any) -> dict[str, Any] | None:
    if not isinstance(metadata, Mapping):
        return None
    raw_policy = metadata.get(DOCUMENT_POLICY_METADATA_KEY)
    if raw_policy is None:
        return None
    return validate_document_policy_v1(policy=raw_policy)


def resolve_document_policy_from_pool_metadata(*, metadata: Any) -> dict[str, Any] | None:
    if not isinstance(metadata, Mapping):
        return None
    raw_policy = metadata.get(DOCUMENT_POLICY_METADATA_KEY)
    if raw_policy is None:
        return None
    return validate_document_policy_v1(policy=raw_policy)


def resolve_document_policy_with_precedence(
    *,
    edge_metadata: Any,
    pool_metadata: Any,
) -> tuple[dict[str, Any] | None, str]:
    edge_policy = resolve_document_policy_from_edge_metadata(metadata=edge_metadata)
    if edge_policy is not None:
        return edge_policy, DOCUMENT_POLICY_RESOLUTION_SOURCE_EDGE

    pool_default_policy = resolve_document_policy_from_pool_metadata(metadata=pool_metadata)
    if pool_default_policy is not None:
        return pool_default_policy, DOCUMENT_POLICY_RESOLUTION_SOURCE_POOL_DEFAULT

    return None, DOCUMENT_POLICY_RESOLUTION_SOURCE_NONE


def _require_object(
    value: Any,
    *,
    field_name: str,
    error_code: str,
    default_empty_object: bool = False,
) -> dict[str, Any]:
    if value is None:
        if default_empty_object:
            return {}
        raise ValueError(f"{error_code}: {field_name} must be an object")
    if not isinstance(value, Mapping):
        raise ValueError(f"{error_code}: {field_name} must be an object")
    return dict(value)


def _require_string(value: Any, *, field_name: str, error_code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{error_code}: {field_name} must be a non-empty string")
    return text
