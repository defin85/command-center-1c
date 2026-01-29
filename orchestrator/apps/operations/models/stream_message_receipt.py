"""StreamMessageReceipt model - idempotency receipts for Redis Streams processing."""

from django.db import models


class StreamMessageReceipt(models.Model):
    """
    Stores receipts for successfully handled Redis Streams messages.

    Uniqueness is enforced by (stream, group, message_id) to guarantee idempotency
    at the Postgres boundary under at-least-once delivery semantics.
    """

    id = models.AutoField(primary_key=True)

    stream = models.CharField(max_length=255)
    group = models.CharField(max_length=255)
    message_id = models.CharField(max_length=64)

    processed_at = models.DateTimeField(auto_now_add=True)

    event_type = models.CharField(max_length=128, blank=True)
    correlation_id = models.CharField(max_length=128, blank=True)
    handler = models.CharField(max_length=128, blank=True)

    class Meta:
        db_table = "stream_message_receipts"
        constraints = [
            models.UniqueConstraint(
                fields=["stream", "group", "message_id"],
                name="uq_stream_message_receipt_stream_group_message_id",
            )
        ]
        indexes = [
            models.Index(fields=["processed_at"]),
            models.Index(fields=["stream", "group"]),
        ]

    def __str__(self) -> str:
        return f"{self.stream}:{self.group}:{self.message_id}"

