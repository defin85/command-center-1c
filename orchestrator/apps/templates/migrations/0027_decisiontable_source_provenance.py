from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("templates", "0026_decisiontable_metadata_context"),
    ]

    operations = [
        migrations.AddField(
            model_name="decisiontable",
            name="source_provenance",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Immutable source provenance for imported or migrated decision revisions.",
            ),
        ),
    ]
