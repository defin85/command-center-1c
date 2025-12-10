"""
Django management command for cleaning up expired files.

Usage:
    python manage.py cleanup_expired_files
    python manage.py cleanup_expired_files --dry-run
    python manage.py cleanup_expired_files --verbose
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.files.models import UploadedFile
from apps.files.services import FileStorageService


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to clean up expired uploaded files."""

    help = 'Delete expired files from storage and database'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about each file',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        verbose = options['verbose']

        self.stdout.write(
            self.style.MIGRATE_HEADING('Cleaning up expired files...')
        )

        # Get expired files
        now = timezone.now()
        expired_files = UploadedFile.objects.filter(expires_at__lte=now)
        total_count = expired_files.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No expired files found.')
            )
            return

        self.stdout.write(
            f'Found {total_count} expired file(s)'
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN - no files will be deleted')
            )

        deleted_count = 0
        failed_count = 0
        total_size = 0

        for uploaded_file in expired_files:
            if verbose:
                self.stdout.write(
                    f'  - {uploaded_file.original_filename} '
                    f'({uploaded_file.size_human}, '
                    f'expired {uploaded_file.expires_at})'
                )

            total_size += uploaded_file.size

            if not dry_run:
                try:
                    if FileStorageService.delete_file(uploaded_file.id):
                        deleted_count += 1
                    else:
                        failed_count += 1
                        logger.warning(
                            f'Failed to delete file: {uploaded_file.id}'
                        )
                except Exception as e:
                    failed_count += 1
                    logger.exception(
                        f'Error deleting file {uploaded_file.id}: {e}'
                    )
            else:
                deleted_count += 1

        # Format total size
        size_mb = total_size / (1024 * 1024)

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Would delete {deleted_count} file(s), '
                    f'freeing {size_mb:.2f} MB'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Deleted {deleted_count} file(s), '
                    f'freed {size_mb:.2f} MB'
                )
            )

            if failed_count > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f'Failed to delete {failed_count} file(s)'
                    )
                )

            # Log summary
            logger.info(
                f'Cleanup completed: {deleted_count} deleted, '
                f'{failed_count} failed, {size_mb:.2f} MB freed'
            )
