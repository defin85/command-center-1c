from __future__ import annotations

from typing import Any


MASTER_DATA_ENTITY_NOT_FOUND = "MASTER_DATA_ENTITY_NOT_FOUND"
MASTER_DATA_BINDING_AMBIGUOUS = "MASTER_DATA_BINDING_AMBIGUOUS"
MASTER_DATA_BINDING_CONFLICT = "MASTER_DATA_BINDING_CONFLICT"


class MasterDataResolveError(Exception):
    def __init__(
        self,
        *,
        code: str,
        detail: str,
        entity_type: str = "",
        canonical_id: str = "",
        target_database_id: str = "",
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.entity_type = entity_type
        self.canonical_id = canonical_id
        self.target_database_id = target_database_id
        self.errors = errors or []

    def to_diagnostic(self) -> dict[str, Any]:
        return {
            "error_code": self.code,
            "entity_type": self.entity_type,
            "canonical_id": self.canonical_id,
            "target_database_id": self.target_database_id,
            "detail": self.detail,
            "errors": self.errors,
        }
