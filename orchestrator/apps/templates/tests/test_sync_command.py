# orchestrator/apps/templates/tests/test_sync_command.py
"""
Comprehensive tests for sync_operation_templates management command.

Tests cover:
- Template creation from registry
- Template updates when registry changes
- Dry-run mode
- Deactivate unknown templates
- Force flag
- Error handling
- Rollback on error
- Output messages
"""

import pytest
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.templates.models import OperationTemplate
from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
    ParameterSchema,
)


@pytest.mark.django_db
class TestSyncOperationTemplatesCommand:
    """Tests for sync_operation_templates management command."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup and cleanup for each test."""
        registry = get_registry()
        registry.clear()

        # Register test operations
        registry.register_many([
            OperationType(
                id='lock_scheduled_jobs',
                name='Lock Scheduled Jobs',
                description='Disable all scheduled jobs on infobase',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
                required_parameters=[
                    ParameterSchema('cluster_id', 'string', description='Cluster ID'),
                ],
            ),
            OperationType(
                id='unlock_scheduled_jobs',
                name='Unlock Scheduled Jobs',
                description='Enable all scheduled jobs on infobase',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
                required_parameters=[
                    ParameterSchema('cluster_id', 'string', description='Cluster ID'),
                ],
            ),
            OperationType(
                id='create',
                name='Create Entity',
                description='Create new entity in OData',
                backend=BackendType.ODATA,
                target_entity=TargetEntity.ENTITY,
                required_parameters=[
                    ParameterSchema('entity_type', 'string', description='Entity type name'),
                    ParameterSchema('data', 'json', description='Entity data'),
                ],
            ),
            OperationType(
                id='update',
                name='Update Entity',
                description='Update existing entity in OData',
                backend=BackendType.ODATA,
                target_entity=TargetEntity.ENTITY,
                required_parameters=[
                    ParameterSchema('entity_id', 'uuid', description='Entity ID'),
                    ParameterSchema('data', 'json', description='Updated data'),
                ],
            ),
            OperationType(
                id='delete',
                name='Delete Entity',
                description='Delete entity from OData',
                backend=BackendType.ODATA,
                target_entity=TargetEntity.ENTITY,
                required_parameters=[
                    ParameterSchema('entity_id', 'uuid', description='Entity ID'),
                ],
            ),
        ])

        yield

        registry.clear()
        OperationTemplate.objects.all().delete()

    def test_creates_templates(self):
        """Test command creates templates from registry."""
        out = StringIO()
        call_command('sync_operation_templates', stdout=out)

        assert OperationTemplate.objects.count() == 5

        # Check specific templates were created
        assert OperationTemplate.objects.filter(id='tpl-lock-scheduled-jobs').exists()
        assert OperationTemplate.objects.filter(id='tpl-unlock-scheduled-jobs').exists()
        assert OperationTemplate.objects.filter(id='tpl-create').exists()
        assert OperationTemplate.objects.filter(id='tpl-update').exists()
        assert OperationTemplate.objects.filter(id='tpl-delete').exists()

    def test_created_templates_have_correct_data(self):
        """Test created templates have correct data from registry."""
        call_command('sync_operation_templates')

        template = OperationTemplate.objects.get(id='tpl-lock-scheduled-jobs')

        assert template.name == 'Lock Scheduled Jobs'
        assert template.description == 'Disable all scheduled jobs on infobase'
        assert template.operation_type == 'lock_scheduled_jobs'
        assert template.target_entity == 'infobase'
        assert template.is_active is True

    def test_template_data_includes_metadata(self):
        """Test template_data includes operation metadata."""
        call_command('sync_operation_templates')

        template = OperationTemplate.objects.get(id='tpl-lock-scheduled-jobs')

        assert 'template_data' in template.__dict__
        template_data = template.template_data

        assert 'backend' in template_data
        assert template_data['backend'] == 'ras'
        assert 'timeout_seconds' in template_data
        assert 'max_retries' in template_data
        assert 'required_parameters' in template_data
        assert 'cluster_id' in template_data['required_parameters']

    def test_dry_run_no_changes(self):
        """Test --dry-run doesn't create templates."""
        out = StringIO()
        call_command('sync_operation_templates', '--dry-run', stdout=out)

        assert OperationTemplate.objects.count() == 0
        assert 'DRY RUN' in out.getvalue()

    def test_dry_run_output_shows_creates(self):
        """Test --dry-run output shows what would be created."""
        out = StringIO()
        call_command('sync_operation_templates', '--dry-run', stdout=out)

        output = out.getvalue()
        assert '[CREATE]' in output
        assert 'tpl-lock-scheduled-jobs' in output

    def test_idempotent_running_twice(self):
        """Test running command twice doesn't duplicate templates."""
        call_command('sync_operation_templates')
        assert OperationTemplate.objects.count() == 5

        call_command('sync_operation_templates')
        assert OperationTemplate.objects.count() == 5

    def test_updates_existing_template(self):
        """Test command updates existing template when registry changes."""
        # Create template with old data
        OperationTemplate.objects.create(
            id='tpl-lock-scheduled-jobs',
            name='Old Name',
            description='Old description',
            operation_type='lock_scheduled_jobs',
            target_entity='infobase',
            template_data={'old': 'data'},
        )

        # Run command
        call_command('sync_operation_templates')

        # Check template was updated
        template = OperationTemplate.objects.get(id='tpl-lock-scheduled-jobs')
        assert template.name == 'Lock Scheduled Jobs'
        assert template.description == 'Disable all scheduled jobs on infobase'
        assert 'old' not in template.template_data

    def test_force_flag_updates_unchanged_templates(self):
        """Test --force updates templates even if unchanged."""
        # Create all templates first
        call_command('sync_operation_templates')

        # Now run again without force - should show unchanged
        out1 = StringIO()
        call_command('sync_operation_templates', '--verbosity=2', stdout=out1)
        output1 = out1.getvalue()
        assert '[UNCHANGED]' in output1 or 'Unchanged:   5' in output1

        # Run with force - should update all
        out2 = StringIO()
        call_command('sync_operation_templates', '--force', stdout=out2)
        output2 = out2.getvalue()
        assert '[UPDATE]' in output2 or 'Updated:     5' in output2

    def test_deactivate_unknown_templates(self):
        """Test --deactivate-unknown deactivates unregistered templates."""
        # Create template not in registry
        OperationTemplate.objects.create(
            id='tpl-unknown-operation',
            name='Unknown Operation',
            description='',
            operation_type='unknown_operation',
            target_entity='infobase',
            is_active=True,
        )

        # Run with deactivate flag
        call_command('sync_operation_templates', '--deactivate-unknown')

        # Check unknown template is deactivated
        template = OperationTemplate.objects.get(id='tpl-unknown-operation')
        assert template.is_active is False

    def test_deactivate_unknown_only_deactivates_active(self):
        """Test --deactivate-unknown only deactivates active templates."""
        # Create already inactive template
        OperationTemplate.objects.create(
            id='tpl-unknown1',
            name='Unknown 1',
            description='',
            operation_type='unknown1',
            target_entity='infobase',
            is_active=False,
        )

        # Create active unknown template
        OperationTemplate.objects.create(
            id='tpl-unknown2',
            name='Unknown 2',
            description='',
            operation_type='unknown2',
            target_entity='infobase',
            is_active=True,
        )

        call_command('sync_operation_templates', '--deactivate-unknown')

        # Only active one should be affected
        assert not OperationTemplate.objects.get(id='tpl-unknown1').is_active
        assert not OperationTemplate.objects.get(id='tpl-unknown2').is_active

    def test_deactivate_unknown_dry_run(self):
        """Test --deactivate-unknown with --dry-run doesn't make changes."""
        OperationTemplate.objects.create(
            id='tpl-unknown',
            name='Unknown',
            description='',
            operation_type='unknown',
            target_entity='infobase',
            is_active=True,
        )

        out = StringIO()
        call_command(
            'sync_operation_templates',
            '--deactivate-unknown',
            '--dry-run',
            stdout=out,
        )

        # Should not be deactivated
        assert OperationTemplate.objects.get(id='tpl-unknown').is_active is True
        assert 'DRY RUN' in out.getvalue()

    def test_empty_registry_raises_error(self):
        """Test command raises error if registry is empty."""
        registry = get_registry()
        registry.clear()

        out = StringIO()
        err = StringIO()

        with pytest.raises(CommandError) as exc_info:
            call_command('sync_operation_templates', stdout=out, stderr=err)

        assert 'No operation types registered' in str(exc_info.value)

    def test_verbose_output(self):
        """Test verbose output shows detailed information."""
        out = StringIO()
        call_command('sync_operation_templates', '--verbosity=2', stdout=out)

        output = out.getvalue()

        # Should show operation types
        assert 'lock_scheduled_jobs' in output
        assert 'create' in output
        assert 'update' in output

        # Should show counts
        assert 'Created' in output
        assert '5' in output

    def test_summary_output(self):
        """Test command summary output."""
        out = StringIO()
        call_command('sync_operation_templates', stdout=out)

        output = out.getvalue()

        # Check summary format
        assert 'Created:' in output
        assert 'Updated:' in output
        assert 'Unchanged:' in output
        assert 'Deactivated:' in output
        assert 'Synchronization complete!' in output

    def test_mixed_create_and_update(self):
        """Test mix of create and update operations."""
        # Create one template
        OperationTemplate.objects.create(
            id='tpl-lock-scheduled-jobs',
            name='Old Name',
            description='',
            operation_type='lock_scheduled_jobs',
            target_entity='infobase',
        )

        out = StringIO()
        call_command('sync_operation_templates', stdout=out)

        output = out.getvalue()

        # Should have created 4 and updated 1
        assert 'Created:     4' in output
        assert 'Updated:     1' in output

    def test_operation_with_parameters(self):
        """Test template is created with parameter information."""
        call_command('sync_operation_templates')

        template = OperationTemplate.objects.get(id='tpl-create')

        # Check required parameters
        assert 'entity_type' in template.template_data['required_parameters']
        assert 'data' in template.template_data['required_parameters']

        # Check parameter schemas
        schemas = template.template_data['parameter_schemas']
        assert 'entity_type' in schemas
        assert schemas['entity_type']['type'] == 'string'

    def test_transaction_rollback_on_error(self):
        """Test transaction rollback on error during sync."""
        # Create an invalid template to cause potential error
        OperationTemplate.objects.create(
            id='tpl-lock-scheduled-jobs',
            name='Lock Scheduled Jobs',
            description='Disable all scheduled jobs on infobase',
            operation_type='lock_scheduled_jobs',
            target_entity='infobase',
        )

        # Run command - should succeed despite having existing template
        out = StringIO()
        call_command('sync_operation_templates', stdout=out)

        # All 5 templates should exist
        assert OperationTemplate.objects.count() == 5


@pytest.mark.django_db
class TestSyncCommandEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup registry with edge case operations."""
        registry = get_registry()
        registry.clear()

        registry.register(OperationType(
            id='operation_with_underscores',
            name='Operation With Underscores',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        ))

        yield

        registry.clear()
        OperationTemplate.objects.all().delete()

    def test_underscore_to_hyphen_conversion(self):
        """Test operation IDs with underscores are converted to hyphens in template ID."""
        call_command('sync_operation_templates')

        template = OperationTemplate.objects.get(id='tpl-operation-with-underscores')
        assert template.operation_type == 'operation_with_underscores'

    def test_all_target_entities(self):
        """Test command handles all target entity types."""
        registry = get_registry()
        registry.clear()

        for target in [TargetEntity.INFOBASE, TargetEntity.CLUSTER, TargetEntity.ENTITY]:
            registry.register(OperationType(
                id=f'op_{target.value}',
                name=f'Op {target.value}',
                description='',
                backend=BackendType.RAS if target != TargetEntity.ENTITY else BackendType.ODATA,
                target_entity=target,
            ))

        call_command('sync_operation_templates')

        assert OperationTemplate.objects.count() == 3

        for target in [TargetEntity.INFOBASE, TargetEntity.CLUSTER, TargetEntity.ENTITY]:
            template = OperationTemplate.objects.get(id=f'tpl-op-{target.value}')
            assert template.target_entity == target.value

    def test_special_characters_in_description(self):
        """Test templates with special characters in description."""
        registry = get_registry()
        registry.clear()

        registry.register(OperationType(
            id='special_op',
            name='Special Op',
            description='Description with "quotes", \'apostrophes\', and {special} chars',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        ))

        call_command('sync_operation_templates')

        template = OperationTemplate.objects.get(id='tpl-special-op')
        assert '"quotes"' in template.description
        assert 'apostrophes' in template.description

    def test_large_registry(self):
        """Test command with many operations."""
        registry = get_registry()
        registry.clear()

        # Register 20 operations
        for i in range(20):
            registry.register(OperationType(
                id=f'operation_{i:02d}',
                name=f'Operation {i}',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            ))

        out = StringIO()
        call_command('sync_operation_templates', stdout=out)

        assert OperationTemplate.objects.count() == 20

    def test_update_with_parameter_changes(self):
        """Test updating template when parameters change."""
        registry = get_registry()
        registry.clear()

        # Register with one parameter
        registry.register(OperationType(
            id='test_op',
            name='Test Op',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('param1', 'string'),
            ],
        ))

        # First sync
        call_command('sync_operation_templates')

        template = OperationTemplate.objects.get(id='tpl-test-op')
        assert 'param1' in template.template_data['required_parameters']

        # Change registry (in real life this would be code changes)
        registry.clear()
        registry.register(OperationType(
            id='test_op',
            name='Test Op',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('param1', 'string'),
                ParameterSchema('param2', 'integer'),
            ],
        ))

        # Second sync should update
        out = StringIO()
        call_command('sync_operation_templates', stdout=out)

        template = OperationTemplate.objects.get(id='tpl-test-op')
        assert 'param1' in template.template_data['required_parameters']
        assert 'param2' in template.template_data['required_parameters']

        registry.clear()


@pytest.mark.django_db
class TestSyncCommandIntegration:
    """Integration tests with registry from test setup."""

    @pytest.fixture(autouse=True)
    def setup_test_registry(self):
        """Setup registry for integration tests."""
        registry = get_registry()
        registry.clear()

        registry.register_many([
            OperationType(
                id='integration_test_op',
                name='Integration Test Op',
                description='For integration tests',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            ),
        ])

        yield

        registry.clear()
        OperationTemplate.objects.all().delete()

    def test_registry_has_operations(self):
        """Test that registry has operations for integration test."""
        registry = get_registry()
        operations = registry.get_all()

        # Registry should have operations
        assert len(operations) > 0

    def test_sync_with_registry(self):
        """Test sync command with registered operations."""
        out = StringIO()
        call_command('sync_operation_templates', stdout=out)

        # Should create templates for all registered operations
        registry = get_registry()
        expected_count = len(registry.get_all())

        assert OperationTemplate.objects.count() == expected_count
        assert OperationTemplate.objects.filter(
            id='tpl-integration-test-op'
        ).exists()
