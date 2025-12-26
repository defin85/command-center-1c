from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("artifacts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="artifactversion",
            name="filename",
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
