from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("databases", "0001_initial"),
        ("operations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Artifact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("kind", models.CharField(choices=[
                    ("extension", "Extension"),
                    ("config_xml", "Config XML"),
                    ("dt_backup", "DT Backup"),
                    ("epf", "EPF"),
                    ("erf", "ERF"),
                    ("ibcmd_package", "IBCMD Package"),
                    ("ras_script", "RAS Script"),
                    ("other", "Other"),
                ], max_length=64)),
                ("is_versioned", models.BooleanField(default=True)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="artifacts_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("name", "kind")},
            },
        ),
        migrations.CreateModel(
            name="ArtifactVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.CharField(max_length=64)),
                ("filename", models.CharField(max_length=255)),
                ("storage_key", models.CharField(max_length=512)),
                ("size", models.BigIntegerField()),
                ("checksum", models.CharField(max_length=128)),
                ("content_type", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("artifact", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versions", to="artifacts.artifact")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="artifact_versions_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("artifact", "version")},
            },
        ),
        migrations.CreateModel(
            name="ArtifactAlias",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("alias", models.CharField(max_length=64)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("artifact", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="aliases", to="artifacts.artifact")),
                ("version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="aliases", to="artifacts.artifactversion")),
            ],
            options={
                "unique_together": {("artifact", "alias")},
            },
        ),
        migrations.CreateModel(
            name="ArtifactUsage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("used_at", models.DateTimeField(auto_now_add=True)),
                ("artifact", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="usage", to="artifacts.artifact")),
                ("database", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="artifact_usage", to="databases.database")),
                ("operation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="artifact_usage", to="operations.batchoperation")),
                ("version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="usage", to="artifacts.artifactversion")),
            ],
            options={
                "ordering": ["-used_at"],
            },
        ),
        migrations.AddIndex(
            model_name="artifact",
            index=models.Index(fields=["kind", "name"], name="artifacts_a_kind_68a1d8_idx"),
        ),
        migrations.AddIndex(
            model_name="artifactalias",
            index=models.Index(fields=["artifact", "alias"], name="artifacts_a_artifac_61cbb0_idx"),
        ),
        migrations.AddIndex(
            model_name="artifactversion",
            index=models.Index(fields=["storage_key"], name="artifacts_a_storage_8f3b9f_idx"),
        ),
        migrations.AddIndex(
            model_name="artifactversion",
            index=models.Index(fields=["artifact", "version"], name="artifacts_a_artifac_6fd42b_idx"),
        ),
        migrations.AddIndex(
            model_name="artifactusage",
            index=models.Index(fields=["artifact", "version"], name="artifacts_a_artifac_9ea109_idx"),
        ),
    ]
