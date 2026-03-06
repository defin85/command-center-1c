from __future__ import annotations

import base64
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
def test_verify_published_documents_uses_utf8_basic_auth_and_reports_missing_table_part(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = Tenant.objects.create(slug=f"verify-{uuid4().hex[:8]}", name="Verify")
    database = _create_database(tenant=tenant, name=f"verify-db-{uuid4().hex[:8]}")
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="ГлавБух",
        ib_password="пароль",
        is_service=True,
    )
    captured_headers: dict[str, str] = {}

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "Ref_Key": "sale-ref-001",
                "Amount": "100.00",
            }

    def _fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
        timeout: tuple[int, int],
    ):
        _ = (url, params, timeout)
        captured_headers.update(headers)
        return _Response()

    monkeypatch.setattr(
        "apps.intercompany_pools.publication_verification.requests.get",
        _fake_get,
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

    expected_auth = "Basic " + base64.b64encode("ГлавБух:пароль".encode("utf-8")).decode("ascii")
    assert captured_headers["Authorization"] == expected_auth
    assert verification["status"] == "failed"
    assert verification["summary"]["verified_documents"] == 1
    assert verification["summary"]["mismatches_count"] == 1
    assert verification["summary"]["mismatches"][0]["database_id"] == str(database.id)
    assert verification["summary"]["mismatches"][0]["entity_name"] == "Document_Sales"
    assert verification["summary"]["mismatches"][0]["field_or_table_path"] == "Goods"
