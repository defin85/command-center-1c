from django.db import migrations, models


def _parse_host_port(value: str):
    if not value:
        return "", None
    if ":" not in value:
        return value, None
    host, port_str = value.rsplit(":", 1)
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        port = None
    return host, port


def _fill_cluster_connection_fields(apps, schema_editor):
    Cluster = apps.get_model("databases", "Cluster")

    for cluster in Cluster.objects.all():
        ras_host, ras_port = _parse_host_port(getattr(cluster, "ras_server", ""))
        updates = {}

        if ras_host:
            updates["ras_host"] = ras_host
        if ras_port:
            updates["ras_port"] = ras_port

        if ras_host:
            updates.setdefault("rmngr_host", ras_host)
            updates.setdefault("ragent_host", ras_host)

        updates.setdefault("ras_port", 1545)
        updates.setdefault("rmngr_port", 1541)
        updates.setdefault("ragent_port", 1540)
        updates.setdefault("rphost_port_from", 1560)
        updates.setdefault("rphost_port_to", 1591)

        if updates:
            Cluster.objects.filter(pk=cluster.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ("databases", "0019_remove_extension_installation"),
    ]

    operations = [
        migrations.AddField(
            model_name="cluster",
            name="ras_host",
            field=models.CharField(
                blank=True,
                default="",
                help_text="RAS host (e.g., localhost, srv1c, 192.168.1.100)",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="cluster",
            name="ras_port",
            field=models.IntegerField(
                blank=True,
                help_text="RAS port (default: 1545)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cluster",
            name="rmngr_host",
            field=models.CharField(
                blank=True,
                default="",
                help_text="RMNGR host (cluster manager)",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="cluster",
            name="rmngr_port",
            field=models.IntegerField(
                blank=True,
                help_text="RMNGR port (default: 1541)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cluster",
            name="ragent_host",
            field=models.CharField(
                blank=True,
                default="",
                help_text="RAGENT host (server agent)",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="cluster",
            name="ragent_port",
            field=models.IntegerField(
                blank=True,
                help_text="RAGENT port (default: 1540)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cluster",
            name="rphost_port_from",
            field=models.IntegerField(
                blank=True,
                help_text="RPHOST port range start (default: 1560)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cluster",
            name="rphost_port_to",
            field=models.IntegerField(
                blank=True,
                help_text="RPHOST port range end (default: 1591)",
                null=True,
            ),
        ),
        migrations.RunPython(_fill_cluster_connection_fields, migrations.RunPython.noop),
    ]
