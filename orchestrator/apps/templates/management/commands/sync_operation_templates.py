"""
Management command to synchronize OperationTemplate with registry.

Usage:
    ./manage.py sync_operation_templates
    ./manage.py sync_operation_templates --dry-run
    ./manage.py sync_operation_templates --deactivate-unknown
    ./manage.py sync_operation_templates --force
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.templates.models import OperationTemplate
from apps.templates.registry import get_registry

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Synchronize OperationTemplate with registered operation types.

    Creates missing templates, updates existing ones, and optionally
    deactivates templates for unregistered operation types.
    """

    help = 'Synchronize OperationTemplate with registered operation types from backends'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--deactivate-unknown',
            action='store_true',
            help='Deactivate templates with unregistered operation types',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if template exists and unchanged',
        )
        # Note: --verbosity is already added by Django's BaseCommand

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        deactivate_unknown = options['deactivate_unknown']
        force = options['force']
        verbosity = options['verbosity']

        registry = get_registry()

        if not registry.get_all():
            raise CommandError(
                "No operation types registered in registry. "
                "Ensure backends are imported and register_operations() is called."
            )

        registered_count = len(registry.get_all())
        self.stdout.write(f"Found {registered_count} registered operation types in registry")

        if verbosity >= 2:
            for op in registry.get_all():
                self.stdout.write(f"  - {op.id}: {op.name} ({op.backend.value})")

        created = 0
        updated = 0
        unchanged = 0
        deactivated = 0
        errors = []

        try:
            with transaction.atomic():
                # Get template data from registry
                templates_data = registry.get_for_template_sync()

                for data in templates_data:
                    template_id = data['id']
                    operation_type = data['operation_type']

                    try:
                        template = OperationTemplate.objects.get(id=template_id)

                        # Check if update needed
                        needs_update = force or self._needs_update(template, data)

                        if needs_update:
                            if dry_run:
                                self.stdout.write(
                                    self.style.WARNING(f"  [UPDATE] {template_id}")
                                )
                            else:
                                for key, value in data.items():
                                    if key != 'id':  # Don't update primary key
                                        setattr(template, key, value)
                                template.save()
                                logger.info(f"Updated OperationTemplate: {template_id}")
                            updated += 1
                        else:
                            if verbosity >= 2:
                                self.stdout.write(f"  [UNCHANGED] {template_id}")
                            unchanged += 1

                    except OperationTemplate.DoesNotExist:
                        if dry_run:
                            self.stdout.write(
                                self.style.SUCCESS(f"  [CREATE] {template_id} ({operation_type})")
                            )
                        else:
                            OperationTemplate.objects.create(**data)
                            logger.info(f"Created OperationTemplate: {template_id}")
                        created += 1

                    except Exception as exc:
                        error_msg = f"Error processing {template_id}: {exc}"
                        errors.append(error_msg)
                        self.stdout.write(self.style.ERROR(f"  [ERROR] {error_msg}"))

                # Handle unknown templates
                if deactivate_unknown:
                    registered_ids = registry.get_ids()
                    # Also get template IDs that we manage
                    managed_ids = {d['id'] for d in templates_data}

                    unknown_templates = OperationTemplate.objects.filter(
                        is_active=True
                    ).exclude(
                        id__in=managed_ids
                    )

                    for template in unknown_templates:
                        if dry_run:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"  [DEACTIVATE] {template.id} "
                                    f"(type: {template.operation_type})"
                                )
                            )
                        else:
                            template.is_active = False
                            template.save(update_fields=['is_active', 'updated_at'])
                            logger.warning(
                                f"Deactivated OperationTemplate: {template.id} "
                                f"(unknown type: {template.operation_type})"
                            )
                        deactivated += 1

                if dry_run:
                    # Rollback in dry-run mode
                    transaction.set_rollback(True)

        except Exception as exc:
            raise CommandError(f"Synchronization failed: {exc}")

        # Summary
        self.stdout.write("")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Created:     {created}")
        self.stdout.write(f"Updated:     {updated}")
        self.stdout.write(f"Unchanged:   {unchanged}")
        self.stdout.write(f"Deactivated: {deactivated}")

        if errors:
            self.stdout.write(f"Errors:      {len(errors)}")
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))

        self.stdout.write("=" * 50)

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN - no changes were made"))
        else:
            self.stdout.write(self.style.SUCCESS("\nSynchronization complete!"))

    def _needs_update(self, template: OperationTemplate, data: dict) -> bool:
        """Check if template needs update by comparing fields."""
        fields_to_check = ['name', 'description', 'operation_type', 'target_entity', 'template_data']

        for field in fields_to_check:
            if field not in data:
                continue
            current = getattr(template, field, None)
            new_value = data[field]

            # Compare JSONField properly
            if field == 'template_data':
                if current != new_value:
                    return True
            elif current != new_value:
                return True

        return False
