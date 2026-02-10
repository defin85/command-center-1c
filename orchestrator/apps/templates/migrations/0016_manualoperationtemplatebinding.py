from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("templates", "0015_remove_action_catalog_surface_and_cleanup"),
        ("tenancy", "0002_seed_default_tenant"),
    ]

    operations = [
        migrations.CreateModel(
            name="ManualOperationTemplateBinding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("manual_operation", models.CharField(max_length=64)),
                ("template_id", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="manual_operation_template_bindings",
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_manual_operation_template_bindings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "manual_operation_template_bindings",
            },
        ),
        migrations.AddConstraint(
            model_name="manualoperationtemplatebinding",
            constraint=models.UniqueConstraint(
                fields=("tenant", "manual_operation"),
                name="manual_op_tpl_binding_tenant_op_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="manualoperationtemplatebinding",
            index=models.Index(fields=["tenant", "manual_operation"], name="manual_op_tpl_tenant_op_idx"),
        ),
        migrations.AddIndex(
            model_name="manualoperationtemplatebinding",
            index=models.Index(fields=["template_id"], name="manual_op_tpl_template_idx"),
        ),
    ]
