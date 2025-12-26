from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0015_alter_batchoperation_operation_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="batchoperation",
            name="operation_type",
            field=models.CharField(
                choices=[
                    ("create", "Create"),
                    ("update", "Update"),
                    ("delete", "Delete"),
                    ("query", "Query"),
                    ("install_extension", "Install Extension"),
                    ("lock_scheduled_jobs", "Lock Scheduled Jobs"),
                    ("unlock_scheduled_jobs", "Unlock Scheduled Jobs"),
                    ("terminate_sessions", "Terminate Sessions"),
                    ("block_sessions", "Block Sessions"),
                    ("unblock_sessions", "Unblock Sessions"),
                    ("sync_cluster", "Sync Cluster"),
                    ("discover_clusters", "Discover Clusters"),
                    ("health_check", "Health Check"),
                    ("ibcmd_backup", "IBCMD Backup"),
                    ("ibcmd_restore", "IBCMD Restore"),
                    ("ibcmd_replicate", "IBCMD Replicate"),
                    ("ibcmd_create", "IBCMD Create"),
                    ("remove_extension", "Remove Extension"),
                    ("config_update", "Update Configuration"),
                    ("config_load", "Load Configuration"),
                    ("config_dump", "Dump Configuration"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
