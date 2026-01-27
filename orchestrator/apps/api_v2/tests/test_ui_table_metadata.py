import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_ui_table_metadata_dbms_users_exists():
    user = User.objects.create_user(username="ui_table_metadata_user", password="pass")
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get("/api/v2/ui/table-metadata/", {"table": "rbac_dbms_users"})
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["table_id"] == "rbac_dbms_users"
    assert isinstance(payload.get("version"), str)
    assert isinstance(payload.get("columns"), list)
    keys = [col.get("key") for col in payload["columns"]]
    assert "db_username" in keys
    assert "cc_user" in keys
    assert "auth_type" in keys
    assert "is_service" in keys
    assert "password" in keys
    assert "actions" in keys


@pytest.mark.django_db
def test_ui_table_metadata_unknown_table_returns_404():
    user = User.objects.create_user(username="ui_table_metadata_user_404", password="pass")
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get("/api/v2/ui/table-metadata/", {"table": "does_not_exist"})
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNKNOWN_TABLE"

