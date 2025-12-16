import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


class FakeRedis:
    def __init__(self, items):
        self._items = items

    def xlen(self, _stream):
        return len(self._items)

    def xrevrange(self, _stream, max="+", min="-", count=50):  # noqa: A002
        # Return newest first
        return list(reversed(self._items))[:count]

    def xrange(self, _stream, min, max, count=1):  # noqa: A002
        for entry_id, fields in self._items:
            if entry_id == min:
                return [(entry_id, fields)]
        return []


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="staff_dlq", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def client(staff_user):
    c = APIClient()
    c.force_authenticate(user=staff_user)
    return c


@pytest.fixture
def fake_items():
    return [
        (
            "1710000000000-0",
            {
                "original_message_id": "orig-1",
                "operation_id": "op-1",
                "error_code": "ENVELOPE_PARSE_ERROR",
                "error_message": "bad json",
                "worker_id": "w1",
                "failed_at": "2025-12-16T10:00:00Z",
            },
        ),
        (
            "1710000001000-0",
            {
                "original_message_id": "orig-2",
                "operation_id": "op-2",
                "error_code": "PUBLISH_ERROR",
                "error_message": "redis down",
                "worker_id": "w2",
                "failed_at": "2025-12-16T10:01:00Z",
            },
        ),
    ]


@pytest.mark.django_db
def test_dlq_list_returns_messages(client, monkeypatch, fake_items):
    from apps.api_v2.views import dlq as dlq_view

    monkeypatch.setattr(dlq_view, "_get_redis_client", lambda: FakeRedis(fake_items))

    resp = client.get("/api/v2/dlq/list/?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["count"] == 2
    assert data["messages"][0]["original_message_id"] in {"orig-2", "orig-1"}


@pytest.mark.django_db
def test_dlq_get_by_dlq_message_id(client, monkeypatch, fake_items):
    from apps.api_v2.views import dlq as dlq_view

    monkeypatch.setattr(dlq_view, "_get_redis_client", lambda: FakeRedis(fake_items))

    resp = client.get("/api/v2/dlq/get/?dlq_message_id=1710000000000-0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dlq_message_id"] == "1710000000000-0"
    assert data["operation_id"] == "op-1"


@pytest.mark.django_db
def test_dlq_retry_enqueues_operation(client, monkeypatch, fake_items):
    from apps.api_v2.views import dlq as dlq_view

    monkeypatch.setattr(dlq_view, "_get_redis_client", lambda: FakeRedis(fake_items))

    class FakeResult:
        success = True
        error = ""

    monkeypatch.setattr(dlq_view.OperationsService, "enqueue_operation", lambda _op_id: FakeResult())

    resp = client.post("/api/v2/dlq/retry/", {"operation_id": "op-1"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["enqueued"] is True

