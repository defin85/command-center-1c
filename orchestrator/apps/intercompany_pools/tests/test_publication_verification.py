from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.odata import ODataDocumentTransportError
from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.publication_auth_mapping import ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED
from apps.intercompany_pools.publication_verification import (
    POOL_PUBLICATION_VERIFICATION_FETCH_FAILED,
    VERIFICATION_STATUS_FAILED,
    verify_published_documents,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, name: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
    )


def _build_document_plan_artifact(
    *,
    database_id: str,
    entity_name: str = "Document_Sales",
    document_key: str = "doc-sale-key",
    required_fields: list[str] | None = None,
    required_table_parts: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "targets": [
            {
                "database_id": database_id,
                "chains": [
                    {
                        "documents": [
                            {
                                "entity_name": entity_name,
                                "idempotency_key": document_key,
                                "completeness_requirements": {
                                    "required_fields": required_fields or ["Amount"],
                                    "required_table_parts": required_table_parts
                                    or {
                                        "Goods": {
                                            "min_rows": 1,
                                            "required_fields": ["Qty"],
                                        }
                                    },
                                },
                            }
                        ]
                    }
                ],
            }
        ]
    }


def _build_publication_results(
    *,
    database_id: str,
    document_key: str = "doc-sale-key",
    document_ref: str = "sale-ref-001",
) -> list[dict[str, object]]:
    return [
        {
            "attempts": [
                {
                    "target_database": database_id,
                    "status": "success",
                    "response_summary": {
                        "successful_document_refs": {
                            document_key: document_ref,
                        }
                    },
                }
            ]
        }
    ]


@pytest.mark.django_db
def test_verify_published_documents_fails_closed_when_service_mapping_is_missing() -> None:
    tenant = Tenant.objects.create(slug=f"verify-{uuid4().hex[:8]}", name="Verify")
    database = _create_database(tenant=tenant, name=f"verify-db-{uuid4().hex[:8]}")

    verification = verify_published_documents(
        tenant_id=str(tenant.id),
        document_plan_artifact=_build_document_plan_artifact(database_id=str(database.id)),
        publication_results=_build_publication_results(database_id=str(database.id)),
    )

    assert verification == {
        "status": VERIFICATION_STATUS_FAILED,
        "summary": {
            "checked_targets": 1,
            "verified_documents": 0,
            "mismatches_count": 1,
            "mismatches": [
                {
                    "database_id": str(database.id),
                    "entity_name": "",
                    "document_idempotency_key": "",
                    "field_or_table_path": "$credentials",
                    "kind": ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
                }
            ],
        },
    }


@pytest.mark.django_db
def test_verify_published_documents_uses_database_transport_options_and_fetches_single_entity_without_expand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = Tenant.objects.create(slug=f"verify-{uuid4().hex[:8]}", name="Verify")
    database = _create_database(tenant=tenant, name=f"verify-db-{uuid4().hex[:8]}")
    database.metadata = {"odata_transport": {"verify_tls": False}}
    database.save(update_fields=["metadata", "updated_at"])
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="ГлавБух",
        ib_password="пароль",
        is_service=True,
    )
    captured: dict[str, object] = {}

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "Ref_Key": "sale-ref-001",
                "Amount": "100.00",
                "Goods": [
                    {
                        "Qty": 1,
                    }
                ],
            }

    class _FakeAdapter:
        def __init__(
            self,
            *,
            base_url: str,
            username: str,
            password: str,
            timeout: int | None = None,
            verify_tls: bool = True,
        ) -> None:
            captured["base_url"] = base_url
            captured["username"] = username
            captured["password"] = password
            captured["timeout"] = timeout
            captured["verify_tls"] = verify_tls

        def fetch_document(self, *, entity_name: str, entity_id: str) -> _Response:
            captured["entity_name"] = entity_name
            captured["entity_id"] = entity_id
            return _Response()

        def __enter__(self) -> "_FakeAdapter":
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    monkeypatch.setattr(
        "apps.intercompany_pools.publication_verification.ODataDocumentAdapter",
        _FakeAdapter,
    )

    verification = verify_published_documents(
        tenant_id=str(tenant.id),
        document_plan_artifact={
            "targets": [
                {
                    "database_id": str(database.id),
                    "chains": [
                        {
                            "documents": [
                                {
                                    "entity_name": "Document_Sales",
                                    "idempotency_key": "doc-sale-key",
                                    "completeness_requirements": {
                                        "required_fields": ["Amount"],
                                        "required_table_parts": {
                                            "Goods": {
                                                "min_rows": 1,
                                                "required_fields": ["Qty"],
                                            }
                                        },
                                    },
                                }
                            ]
                        }
                    ],
                }
            ]
        },
        publication_results=[
            {
                "attempts": [
                    {
                        "target_database": str(database.id),
                        "status": "success",
                        "response_summary": {
                            "successful_document_refs": {
                                "doc-sale-key": "sale-ref-001",
                            }
                        },
                    }
                ]
            }
        ],
    )

    assert captured["base_url"] == database.odata_url
    assert captured["username"] == "ГлавБух"
    assert captured["password"] == "пароль"
    assert captured["timeout"] == database.connection_timeout
    assert captured["verify_tls"] is False
    assert captured["entity_name"] == "Document_Sales"
    assert captured["entity_id"] == "guid'sale-ref-001'"
    assert verification["status"] == "passed"
    assert verification["summary"]["verified_documents"] == 1
    assert verification["summary"]["mismatches_count"] == 0
    assert verification["summary"]["mismatches"] == []


@pytest.mark.django_db
def test_verify_published_documents_returns_failed_summary_for_payload_completeness_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = Tenant.objects.create(slug=f"verify-{uuid4().hex[:8]}", name="Verify")
    database = _create_database(tenant=tenant, name=f"verify-db-{uuid4().hex[:8]}")
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="svc-user",
        ib_password="svc-pass",
        is_service=True,
    )

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "Ref_Key": "sale-ref-001",
                "Amount": "100.00",
                "Goods": [],
            }

    class _FakeAdapter:
        def __init__(
            self,
            *,
            base_url: str,
            username: str,
            password: str,
            timeout: int | None = None,
            verify_tls: bool = True,
        ) -> None:
            self.base_url = base_url
            self.username = username
            self.password = password
            self.timeout = timeout
            self.verify_tls = verify_tls

        def fetch_document(self, *, entity_name: str, entity_id: str) -> _Response:
            assert entity_name == "Document_Sales"
            assert entity_id == "guid'sale-ref-001'"
            return _Response()

        def __enter__(self) -> "_FakeAdapter":
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    monkeypatch.setattr(
        "apps.intercompany_pools.publication_verification.ODataDocumentAdapter",
        _FakeAdapter,
    )

    verification = verify_published_documents(
        tenant_id=str(tenant.id),
        document_plan_artifact=_build_document_plan_artifact(database_id=str(database.id)),
        publication_results=_build_publication_results(database_id=str(database.id)),
    )

    assert verification == {
        "status": VERIFICATION_STATUS_FAILED,
        "summary": {
            "checked_targets": 1,
            "verified_documents": 1,
            "mismatches_count": 1,
            "mismatches": [
                {
                    "database_id": str(database.id),
                    "entity_name": "Document_Sales",
                    "document_idempotency_key": "doc-sale-key",
                    "field_or_table_path": "Goods",
                    "kind": "missing_table_part",
                }
            ],
        },
    }


@pytest.mark.django_db
def test_verify_published_documents_returns_failed_summary_for_document_fetch_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = Tenant.objects.create(slug=f"verify-{uuid4().hex[:8]}", name="Verify")
    database = _create_database(tenant=tenant, name=f"verify-db-{uuid4().hex[:8]}")
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="svc-user",
        ib_password="svc-pass",
        is_service=True,
    )

    class _FakeAdapter:
        def __init__(
            self,
            *,
            base_url: str,
            username: str,
            password: str,
            timeout: int | None = None,
            verify_tls: bool = True,
        ) -> None:
            self.base_url = base_url
            self.username = username
            self.password = password
            self.timeout = timeout
            self.verify_tls = verify_tls

        def fetch_document(self, *, entity_name: str, entity_id: str) -> None:
            assert entity_name == "Document_Sales"
            assert entity_id == "guid'sale-ref-001'"
            raise ODataDocumentTransportError("network timeout")

        def __enter__(self) -> "_FakeAdapter":
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    monkeypatch.setattr(
        "apps.intercompany_pools.publication_verification.ODataDocumentAdapter",
        _FakeAdapter,
    )

    verification = verify_published_documents(
        tenant_id=str(tenant.id),
        document_plan_artifact=_build_document_plan_artifact(database_id=str(database.id)),
        publication_results=_build_publication_results(database_id=str(database.id)),
    )

    assert verification == {
        "status": VERIFICATION_STATUS_FAILED,
        "summary": {
            "checked_targets": 1,
            "verified_documents": 0,
            "mismatches_count": 1,
            "mismatches": [
                {
                    "database_id": str(database.id),
                    "entity_name": "Document_Sales",
                    "document_idempotency_key": "doc-sale-key",
                    "field_or_table_path": "$document",
                    "kind": POOL_PUBLICATION_VERIFICATION_FETCH_FAILED,
                }
            ],
        },
    }
