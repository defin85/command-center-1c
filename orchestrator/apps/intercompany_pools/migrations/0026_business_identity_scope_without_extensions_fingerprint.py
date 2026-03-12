from django.db import migrations, models


def _deduplicate_business_identity_scope_state(apps, schema_editor):
    snapshot_model = apps.get_model("intercompany_pools", "PoolODataMetadataCatalogSnapshot")
    resolution_model = apps.get_model("intercompany_pools", "PoolODataMetadataCatalogScopeResolution")
    db_alias = schema_editor.connection.alias

    grouped_snapshot_ids: dict[tuple[str, str, str, str], str] = {}
    grouped_snapshots = (
        snapshot_model.objects.using(db_alias)
        .all()
        .order_by("-is_current", "-fetched_at", "-updated_at", "-created_at", "id")
    )
    for snapshot in grouped_snapshots.iterator():
        key = (
            str(snapshot.tenant_id),
            str(snapshot.config_name),
            str(snapshot.config_version),
            str(snapshot.catalog_version),
        )
        survivor_id = grouped_snapshot_ids.setdefault(key, str(snapshot.id))
        if survivor_id == str(snapshot.id):
            continue
        resolution_model.objects.using(db_alias).filter(snapshot_id=snapshot.id).update(
            snapshot_id=survivor_id
        )
        snapshot_model.objects.using(db_alias).filter(id=snapshot.id).delete()

    grouped_resolution_ids: dict[tuple[str, str, str, str], str] = {}
    grouped_resolutions = (
        resolution_model.objects.using(db_alias)
        .all()
        .order_by("-confirmed_at", "-updated_at", "-created_at", "id")
    )
    for resolution in grouped_resolutions.iterator():
        key = (
            str(resolution.tenant_id),
            str(resolution.database_id),
            str(resolution.config_name),
            str(resolution.config_version),
        )
        survivor_id = grouped_resolution_ids.setdefault(key, str(resolution.id))
        if survivor_id == str(resolution.id):
            continue
        resolution_model.objects.using(db_alias).filter(id=resolution.id).delete()

    resolution_snapshot_ids = set(
        resolution_model.objects.using(db_alias).values_list("snapshot_id", flat=True)
    )
    latest_database_by_snapshot = {}
    latest_resolutions = (
        resolution_model.objects.using(db_alias)
        .order_by("snapshot_id", "-confirmed_at", "-updated_at", "-created_at", "id")
    )
    for resolution in latest_resolutions.iterator():
        latest_database_by_snapshot.setdefault(resolution.snapshot_id, resolution.database_id)

    for snapshot in snapshot_model.objects.using(db_alias).all().iterator():
        updates = {}
        should_be_current = snapshot.id in resolution_snapshot_ids
        if snapshot.is_current != should_be_current:
            updates["is_current"] = should_be_current
        latest_database_id = latest_database_by_snapshot.get(snapshot.id)
        if latest_database_id and snapshot.database_id != latest_database_id:
            updates["database_id"] = latest_database_id
        if updates:
            snapshot_model.objects.using(db_alias).filter(id=snapshot.id).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('databases', '0029_extensionflagspolicy'),
        ('intercompany_pools', '0025_poolworkflowbinding'),
        ('tenancy', '0003_alter_tenant_options_alter_tenantmember_options_and_more'),
    ]

    operations = [
        migrations.RunPython(
            _deduplicate_business_identity_scope_state,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name='poolodatametadatacatalogscoperesolution',
            name='uniq_pool_meta_catalog_scope_resolution',
        ),
        migrations.RemoveConstraint(
            model_name='poolodatametadatacatalogsnapshot',
            name='uniq_pool_meta_catalog_snapshot_shared_version',
        ),
        migrations.RemoveIndex(
            model_name='poolodatametadatacatalogscoperesolution',
            name='pool_odata__tenant__67809e_idx',
        ),
        migrations.RemoveIndex(
            model_name='poolodatametadatacatalogsnapshot',
            name='pool_odata__tenant__d1783a_idx',
        ),
        migrations.AddIndex(
            model_name='poolodatametadatacatalogscoperesolution',
            index=models.Index(fields=['tenant', 'config_name', 'config_version'], name='pool_odata__tenant__39fb28_idx'),
        ),
        migrations.AddIndex(
            model_name='poolodatametadatacatalogsnapshot',
            index=models.Index(fields=['tenant', 'config_name', 'config_version', 'is_current'], name='pool_odata__tenant__b947a6_idx'),
        ),
        migrations.AddConstraint(
            model_name='poolodatametadatacatalogscoperesolution',
            constraint=models.UniqueConstraint(fields=('tenant', 'database', 'config_name', 'config_version'), name='uniq_pool_meta_catalog_scope_resolution'),
        ),
        migrations.AddConstraint(
            model_name='poolodatametadatacatalogsnapshot',
            constraint=models.UniqueConstraint(fields=('tenant', 'config_name', 'config_version', 'catalog_version'), name='uniq_pool_meta_catalog_snapshot_shared_version'),
        ),
    ]
