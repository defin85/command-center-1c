import pytest
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_events_pending_counts_exclude_poison_events():
    from apps.operations.models import FailedEvent

    FailedEvent.objects.create(
        channel="events:test",
        event_type="test.event",
        correlation_id="corr-pending",
        payload={"ok": True},
        kind=FailedEvent.KIND_PUBLISH_FAILURE,
        source_service="worker",
        original_timestamp=timezone.now(),
        status=FailedEvent.STATUS_PENDING,
    )

    FailedEvent.objects.create(
        channel="events:test",
        event_type="test.event",
        correlation_id="corr-failed",
        payload={"ok": False},
        kind=FailedEvent.KIND_PUBLISH_FAILURE,
        source_service="worker",
        original_timestamp=timezone.now(),
        status=FailedEvent.STATUS_FAILED,
    )

    FailedEvent.objects.create(
        channel="events:worker:cluster-synced",
        event_type="cluster.synced",
        correlation_id="corr-poison",
        payload={"reason": "invalid_json_payload"},
        kind=FailedEvent.KIND_POISON_MESSAGE,
        source_service="event_subscriber",
        original_timestamp=timezone.now(),
        status=FailedEvent.STATUS_FAILED,
        retry_count=0,
        max_retries=0,
    )

    client = APIClient()
    resp = client.get("/api/v2/events/pending/")
    assert resp.status_code == 200
    data = resp.json()

    assert data["pending_count"] == 1
    assert data["failed_count"] == 1
    assert data["poison_count"] == 1

