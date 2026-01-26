from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion
from encrypted_model_fields.fields import EncryptedCharField


class Migration(migrations.Migration):

    dependencies = [
        ("databases", "0024_rename_databases_ex_updated_95f8f9_idx_databases_e_updated_d4ad20_idx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DbmsUserMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("db_username", models.CharField(max_length=128)),
                ("db_password", EncryptedCharField(blank=True, max_length=255)),
                (
                    "auth_type",
                    models.CharField(
                        choices=[("local", "Local"), ("service", "Service"), ("other", "Other")],
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
                        related_name="dbms_user_mappings_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "database",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dbms_user_mappings",
                        to="databases.database",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dbms_user_mappings_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dbms_user_mappings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "databases_dbms_user_mappings",
            },
        ),
        migrations.AddIndex(
            model_name="dbmsusermapping",
            index=models.Index(fields=["database", "is_service"], name="dbms_map_db_svc_idx"),
        ),
        migrations.AddIndex(
            model_name="dbmsusermapping",
            index=models.Index(fields=["database", "user"], name="dbms_map_db_user_idx"),
        ),
        migrations.AddConstraint(
            model_name="dbmsusermapping",
            constraint=models.UniqueConstraint(
                fields=("database", "user"),
                condition=Q(user__isnull=False),
                name="dbms_map_unique_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="dbmsusermapping",
            constraint=models.UniqueConstraint(
                fields=("database",),
                condition=Q(is_service=True),
                name="dbms_map_unique_service",
            ),
        ),
        migrations.AddConstraint(
            model_name="dbmsusermapping",
            constraint=models.CheckConstraint(
                check=Q(user__isnull=False) | Q(is_service=True),
                name="dbms_map_user_or_service",
            ),
        ),
    ]
