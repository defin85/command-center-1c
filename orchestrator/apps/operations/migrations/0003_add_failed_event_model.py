# Generated migration for FailedEvent model
# Created 2025-11-28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0002_alter_batchoperation_operation_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="FailedEvent",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("channel", models.CharField(db_index=True, max_length=255)),
                ("event_type", models.CharField(max_length=100)),
                (
                    "correlation_id",
                    models.CharField(db_index=True, max_length=64),
                ),
                ("payload", models.JSONField()),
                ("source_service", models.CharField(max_length=50)),
                ("original_timestamp", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("replayed", "Replayed"),
                            ("failed", "Permanently Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("retry_count", models.IntegerField(default=0)),
                ("max_retries", models.IntegerField(default=5)),
                ("last_error", models.TextField(blank=True)),
                ("replayed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Failed Event",
                "verbose_name_plural": "Failed Events",
                "db_table": "failed_events",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="failedevent",
            index=models.Index(fields=["status", "created_at"], name="failed_even_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="failedevent",
            index=models.Index(fields=["correlation_id"], name="failed_even_correl_idx"),
        ),
        migrations.AddIndex(
            model_name="failedevent",
            index=models.Index(fields=["channel", "status"], name="failed_even_channel_status_idx"),
        ),
    ]
