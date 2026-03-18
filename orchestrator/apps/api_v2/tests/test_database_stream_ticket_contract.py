import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.api_v2.views.databases.common import build_database_stream_active_key


class FakeRedis:
    def __init__(self):
        self._values = {}
        self._ttls = {}

    def seed(self, key: str, value: dict, ttl: int = 45) -> None:
        self._values[key] = json.dumps(value)
        self._ttls[key] = ttl

    def ttl(self, key: str) -> int:
        return self._ttls.get(key, -1)

    def get(self, key: str):
        return self._values.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._values[key] = value
        self._ttls[key] = ttl

    def close(self) -> None:
        return None


@pytest.fixture
def staff_user():
    return User.objects.create_user(username="db_stream_staff", password="pass", is_staff=True)


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.mark.django_db
def test_database_stream_ticket_requires_client_instance_id(staff_client):
    response = staff_client.post("/api/v2/databases/stream-ticket/", {}, format="json")

    assert response.status_code == 400
    assert "client_instance_id" in response.json()


@pytest.mark.django_db
def test_database_stream_ticket_keeps_independent_client_instances_separate(staff_client, staff_user):
    fake_redis = FakeRedis()
    fake_redis.seed(
        build_database_stream_active_key(
            user_id=staff_user.id,
            client_instance_id="browser-a",
            cluster_id=None,
        ),
        {
            "session_id": "session-a",
            "lease_id": "lease-a",
            "client_instance_id": "browser-a",
            "scope": "__all__",
        },
    )

    with patch("apps.api_v2.views.databases.streaming._get_redis_connection", return_value=fake_redis):
        response = staff_client.post(
            "/api/v2/databases/stream-ticket/",
            {"client_instance_id": "browser-b"},
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["client_instance_id"] == "browser-b"
    assert payload["scope"] == "__all__"
    assert payload["session_id"]
    assert payload["lease_id"]


@pytest.mark.django_db
def test_database_stream_ticket_returns_conflict_metadata_for_same_client_instance(staff_client, staff_user):
    fake_redis = FakeRedis()
    fake_redis.seed(
        build_database_stream_active_key(
            user_id=staff_user.id,
            client_instance_id="browser-a",
            cluster_id=None,
        ),
        {
            "session_id": "session-a",
            "lease_id": "lease-a",
            "client_instance_id": "browser-a",
            "scope": "__all__",
        },
        ttl=37,
    )

    with patch("apps.api_v2.views.databases.streaming._get_redis_connection", return_value=fake_redis):
        response = staff_client.post(
            "/api/v2/databases/stream-ticket/",
            {"client_instance_id": "browser-a"},
            format="json",
        )

    assert response.status_code == 429
    assert response["Retry-After"] == "37"
    payload = response.json()
    assert payload["error"]["code"] == "STREAM_ALREADY_ACTIVE"
    assert payload["error"]["details"] == {
        "retry_after": 37,
        "client_instance_id": "browser-a",
        "scope": "__all__",
        "active_session_id": "session-a",
        "active_lease_id": "lease-a",
        "recovery_supported": True,
    }


@pytest.mark.django_db
def test_database_stream_ticket_allows_explicit_recovery_for_same_session(staff_client, staff_user):
    fake_redis = FakeRedis()
    fake_redis.seed(
        build_database_stream_active_key(
            user_id=staff_user.id,
            client_instance_id="browser-a",
            cluster_id=None,
        ),
        {
            "session_id": "session-a",
            "lease_id": "lease-a",
            "client_instance_id": "browser-a",
            "scope": "__all__",
        },
        ttl=37,
    )

    with patch("apps.api_v2.views.databases.streaming._get_redis_connection", return_value=fake_redis):
        response = staff_client.post(
            "/api/v2/databases/stream-ticket/",
            {
                "client_instance_id": "browser-a",
                "session_id": "session-a",
                "recovery": True,
            },
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["client_instance_id"] == "browser-a"
    assert payload["session_id"] == "session-a"
    assert payload["lease_id"] != "lease-a"
    assert payload["message"] == "Database stream recovery ticket issued"
