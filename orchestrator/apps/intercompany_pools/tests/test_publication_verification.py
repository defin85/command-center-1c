from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.publication_verification import verify_published_documents
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
