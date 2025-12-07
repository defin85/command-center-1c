"""
Management command to reset stuck cluster sync statuses.

Usage:
    python manage.py reset_stuck_clusters
    python manage.py reset_stuck_clusters --cluster-id=UUID
    python manage.py reset_stuck_clusters --all
"""

from django.core.management.base import BaseCommand, CommandError

from apps.databases.models import Cluster


class Command(BaseCommand):
    help = 'Reset stuck cluster sync statuses to pending'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cluster-id',
            type=str,
            help='Reset specific cluster by UUID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Reset all clusters (not just stuck ones)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without making changes',
        )

    def handle(self, *args, **options):
        cluster_id = options.get('cluster_id')
        reset_all = options.get('all')
        dry_run = options.get('dry_run')

        if cluster_id:
            # Reset specific cluster
            try:
                cluster = Cluster.objects.get(id=cluster_id)
            except Cluster.DoesNotExist:
                raise CommandError(f'Cluster with id={cluster_id} not found')

            if dry_run:
                self.stdout.write(
                    f'Would reset: {cluster.name} '
                    f'(status: {cluster.last_sync_status})'
                )
            else:
                old_status = cluster.last_sync_status
                cluster.last_sync_status = 'pending'
                cluster.last_sync_error = ''
                cluster.save(update_fields=['last_sync_status', 'last_sync_error'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Reset: {cluster.name} ({old_status} -> pending)'
                    )
                )
        elif reset_all:
            # Reset all clusters
            clusters = Cluster.objects.exclude(last_sync_status='pending')
            count = clusters.count()

            if dry_run:
                for cluster in clusters:
                    self.stdout.write(
                        f'Would reset: {cluster.name} '
                        f'(status: {cluster.last_sync_status})'
                    )
                self.stdout.write(f'\nTotal: {count} clusters')
            else:
                for cluster in clusters:
                    old_status = cluster.last_sync_status
                    cluster.last_sync_status = 'pending'
                    cluster.last_sync_error = ''
                    cluster.save(update_fields=['last_sync_status', 'last_sync_error'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Reset: {cluster.name} ({old_status} -> pending)'
                        )
                    )
                self.stdout.write(
                    self.style.SUCCESS(f'\nReset {count} clusters')
                )
        else:
            # Reset stuck clusters (failed or pending for too long) to success
            stuck_clusters = Cluster.objects.filter(last_sync_status__in=['pending', 'failed'])
            count = stuck_clusters.count()

            if count == 0:
                self.stdout.write(
                    self.style.SUCCESS('No stuck clusters found')
                )
                return

            if dry_run:
                for cluster in stuck_clusters:
                    self.stdout.write(
                        f'Would reset: {cluster.name} (status: {cluster.last_sync_status})'
                    )
                self.stdout.write(f'\nTotal: {count} stuck clusters')
            else:
                for cluster in stuck_clusters:
                    old_status = cluster.last_sync_status
                    cluster.last_sync_status = 'success'
                    cluster.last_sync_error = ''
                    cluster.save(update_fields=['last_sync_status', 'last_sync_error'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Reset: {cluster.name} ({old_status} -> success)'
                        )
                    )
                self.stdout.write(
                    self.style.SUCCESS(f'\nReset {count} stuck clusters')
                )
