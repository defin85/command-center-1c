from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("templates", "0025_decisiontable"),
    ]

    operations = [
        migrations.AddField(
            model_name="decisiontable",
            name="metadata_context",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Immutable metadata snapshot provenance for metadata-aware decisions.",
            ),
        ),
    ]
