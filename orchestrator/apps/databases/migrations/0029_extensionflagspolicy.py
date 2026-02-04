# Generated manually for change: update-extensions-flags-policy-and-actions

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("databases", "0028_migrate_ibcmd_connection_profile_v2"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenancy", "0003_alter_tenant_options_alter_tenantmember_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExtensionFlagsPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("extension_name", models.CharField(db_index=True, max_length=255)),
                ("active", models.BooleanField(blank=True, null=True)),
                ("safe_mode", models.BooleanField(blank=True, null=True)),
                ("unsafe_action_protection", models.BooleanField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="extensions_flags_policies_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="extensions_flags_policies",
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="extensions_flags_policies_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "extensions_flags_policies",
            },
        ),
        migrations.AddConstraint(
            model_name="extensionflagspolicy",
            constraint=models.UniqueConstraint(
                fields=("tenant", "extension_name"),
                name="extensions_flags_policy_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="extensionflagspolicy",
            index=models.Index(fields=["tenant", "extension_name"], name="ext_flags_policy_tenant_name"),
        ),
    ]
