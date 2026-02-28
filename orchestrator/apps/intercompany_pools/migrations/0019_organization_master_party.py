from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("intercompany_pools", "0018_poolmasterdatabinding"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="master_party",
            field=models.OneToOneField(
                blank=True,
                help_text="Canonical party binding for organization-level publication data (MVP 1:1).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="organization_binding",
                to="intercompany_pools.poolmasterparty",
            ),
        ),
    ]
