from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("databases", "0016_alter_cluster_cluster_service_url"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InfobaseUserMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ib_username", models.CharField(max_length=128)),
                ("ib_display_name", models.CharField(blank=True, max_length=255)),
                ("ib_roles", models.JSONField(blank=True, default=list)),
                (
                    "auth_type",
                    models.CharField(
                        choices=[
                            ("local", "Local"),
                            ("ad", "Active Directory"),
                            ("service", "Service"),
                            ("other", "Other"),
                        ],
                        default="local",
                        max_length=32,
                    ),
                ),
                ("is_service", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ib_user_mappings_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "database",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ib_user_mappings",
                        to="databases.database",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ib_user_mappings_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ib_user_mappings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "databases_ib_user_mappings",
                "unique_together": {("database", "ib_username")},
                "indexes": [
                    models.Index(fields=["database", "ib_username"], name="ib_user_db_name_idx"),
                    models.Index(fields=["database", "auth_type"], name="ib_user_db_auth_idx"),
                ],
            },
        ),
    ]
