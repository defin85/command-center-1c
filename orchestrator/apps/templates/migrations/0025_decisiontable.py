from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("templates", "0024_workflowexecution_error_diagnostics"),
    ]

    operations = [
        migrations.CreateModel(
            name="DecisionTable",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("decision_table_id", models.CharField(help_text="Stable decision table key", max_length=200)),
                ("decision_key", models.CharField(help_text="Business decision capability key", max_length=200)),
                ("name", models.CharField(help_text="Decision table name", max_length=200)),
                ("description", models.TextField(blank=True, help_text="Decision table description")),
                ("inputs", models.JSONField(blank=True, default=list)),
                ("outputs", models.JSONField(blank=True, default=list)),
                ("rules", models.JSONField(blank=True, default=list)),
                ("hit_policy", models.CharField(default="first_match", max_length=32)),
                ("validation_mode", models.CharField(default="fail_closed", max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version_number", models.PositiveIntegerField(default=1, help_text="Decision revision number (auto-incremented by helper service)")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_decision_tables", to=settings.AUTH_USER_MODEL)),
                ("parent_version", models.ForeignKey(blank=True, help_text="Parent decision revision if this is a new version", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="child_versions", to="templates.decisiontable")),
            ],
            options={
                "db_table": "workflow_decision_tables",
                "ordering": ["decision_table_id", "-version_number", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="decisiontable",
            index=models.Index(fields=["decision_key", "is_active"], name="wf_decision_key_active_idx"),
        ),
        migrations.AddIndex(
            model_name="decisiontable",
            index=models.Index(fields=["decision_table_id", "-version_number"], name="wf_decision_id_ver_idx"),
        ),
        migrations.AddConstraint(
            model_name="decisiontable",
            constraint=models.UniqueConstraint(fields=("decision_table_id", "version_number"), name="unique_decision_table_revision"),
        ),
    ]
