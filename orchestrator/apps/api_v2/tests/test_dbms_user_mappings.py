import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database


@pytest.mark.django_db
def test_dbms_user_mappings_crud():
    admin = User.objects.create_user(username="admin", password="pass", is_staff=True)
    c = APIClient()
    c.force_authenticate(user=admin)

    db = Database.objects.create(
        name="db-1",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="",
        password="",
    )

    create_service = c.post(
        "/api/v2/databases/create-dbms-user/",
        {
            "database_id": str(db.id),
            "is_service": True,
            "db_username": "postgres",
            "db_password": "secret",
        },
        format="json",
    )
    assert create_service.status_code == 201
    service_payload = create_service.json()
    assert service_payload["database_id"] == str(db.id)
    assert service_payload["is_service"] is True
    assert service_payload["db_username"] == "postgres"
    assert service_payload["db_password_configured"] is True
    assert service_payload["user"] is None

    create_service_dupe = c.post(
        "/api/v2/databases/create-dbms-user/",
        {
            "database_id": str(db.id),
            "is_service": True,
            "db_username": "postgres2",
        },
        format="json",
    )
    assert create_service_dupe.status_code == 409

    user = User.objects.create_user(username="u1", password="pass")
    create_actor_missing_user = c.post(
        "/api/v2/databases/create-dbms-user/",
        {
            "database_id": str(db.id),
            "db_username": "u",
        },
        format="json",
    )
    assert create_actor_missing_user.status_code == 400

    create_actor = c.post(
        "/api/v2/databases/create-dbms-user/",
        {
            "database_id": str(db.id),
            "user_id": user.id,
            "db_username": "u",
            "db_password": "p",
        },
        format="json",
    )
    assert create_actor.status_code == 201
    actor_payload = create_actor.json()
    assert actor_payload["user"]["id"] == user.id
    assert actor_payload["db_username"] == "u"

    list_resp = c.get("/api/v2/databases/list-dbms-users/", {"database_id": str(db.id)})
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["count"] == 2
    assert payload["total"] == 2

    set_pwd = c.post(
        "/api/v2/databases/set-dbms-user-password/",
        {"id": actor_payload["id"], "password": "new"},
        format="json",
    )
    assert set_pwd.status_code == 200
    assert set_pwd.json()["db_password_configured"] is True

    reset_pwd = c.post(
        "/api/v2/databases/reset-dbms-user-password/",
        {"id": actor_payload["id"]},
        format="json",
    )
    assert reset_pwd.status_code == 200

    delete_resp = c.post(
        "/api/v2/databases/delete-dbms-user/",
        {"id": actor_payload["id"]},
        format="json",
    )
    assert delete_resp.status_code == 200

