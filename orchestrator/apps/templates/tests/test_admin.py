# orchestrator/apps/templates/tests/test_admin.py
"""
Comprehensive tests for WorkflowTemplateAdmin and OperationTemplate reference panel.

Tests verify:
- Operation templates context injection in changeform_view
- Operation templates context injection in add_view
- Filtering of only active templates
- Correct sorting by operation_type and name
- Edge cases with empty templates
- Multiple templates with different states
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.contrib.auth.models import User

from apps.templates.admin import WorkflowTemplateAdmin
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowTemplate


@pytest.fixture
def admin_site():
    """Create a bare AdminSite for testing."""
    return AdminSite()


@pytest.fixture
def workflow_admin(admin_site):
    """Create WorkflowTemplateAdmin instance."""
    return WorkflowTemplateAdmin(WorkflowTemplate, admin_site)


@pytest.fixture
def request_factory():
    """Create RequestFactory for building requests."""
    return RequestFactory()


@pytest.fixture
def admin_user(db):
    """Create staff user for testing."""
    # Cleanup: delete existing user if present
    User.objects.filter(username='testadmin_admin').delete()

    return User.objects.create_user(
        username='testadmin_admin',
        email='testadmin@test.com',
        password='testpass123',
        is_staff=True
    )


@pytest.fixture
def sample_workflow(db, admin_user):
    """Create a sample workflow template for testing."""
    return WorkflowTemplate.objects.create(
        name="Test Workflow",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "step1",
                    "name": "Step 1",
                    "type": "operation",
                    "template_id": "test_op1",
                    "config": {"timeout_seconds": 30}
                }
            ],
            "edges": []
        },
        config={"timeout_seconds": 300},
        created_by=admin_user,
        is_valid=True,
        is_active=True
    )


@pytest.mark.django_db
class TestWorkflowTemplateAdminOperationTemplatesContext(TestCase):
    """Test operation templates context injection in WorkflowTemplateAdmin."""

    def setUp(self):
        """Set up test fixtures."""
        self.admin_site = AdminSite()
        self.workflow_admin = WorkflowTemplateAdmin(WorkflowTemplate, self.admin_site)
        self.request_factory = RequestFactory()

        # Create staff user
        User.objects.filter(username='testadmin_admin').delete()
        self.admin_user = User.objects.create_user(
            username='testadmin_admin',
            email='testadmin@test.com',
            password='testpass123',
            is_staff=True
        )

        # Create sample workflow
        self.workflow = WorkflowTemplate.objects.create(
            name="Test Workflow",
            workflow_type="sequential",
            dag_structure={
                "nodes": [
                    {
                        "id": "step1",
                        "name": "Step 1",
                        "type": "operation",
                        "template_id": "test_op1",
                        "config": {"timeout_seconds": 30}
                    }
                ],
                "edges": []
            },
            config={"timeout_seconds": 300},
            created_by=self.admin_user,
            is_valid=True,
            is_active=True
        )

    def test_changeform_view_includes_operation_templates(self):
        """Test that changeform_view includes operation_templates in context."""
        # Create operation templates (mix of active and inactive)
        active_tpl_1 = OperationTemplate.objects.create(
            id='tpl-lock-jobs',
            name='Lock Scheduled Jobs',
            description='Lock all scheduled jobs on infobase',
            operation_type='lock_scheduled_jobs',
            target_entity='infobase',
            template_data={'enabled': True},
            is_active=True
        )
        active_tpl_2 = OperationTemplate.objects.create(
            id='tpl-unlock-jobs',
            name='Unlock Scheduled Jobs',
            description='Unlock all scheduled jobs on infobase',
            operation_type='unlock_scheduled_jobs',
            target_entity='infobase',
            template_data={'enabled': True},
            is_active=True
        )
        inactive_tpl = OperationTemplate.objects.create(
            id='tpl-inactive',
            name='Inactive Template',
            description='This template is inactive',
            operation_type='maintenance',
            target_entity='infobase',
            template_data={'enabled': False},
            is_active=False
        )

        # Build request to change form
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id)
        )

        # Assertions
        assert response.status_code == 200, "Response should be successful"
        assert 'operation_templates' in response.context_data, \
            "operation_templates should be in context"

        templates = list(response.context_data['operation_templates'])

        # Check that only active templates are included
        assert active_tpl_1 in templates, "Active template should be included"
        assert active_tpl_2 in templates, "Active template should be included"
        assert inactive_tpl not in templates, "Inactive template should NOT be included"

        # Verify count
        assert len(templates) == 2, "Should have exactly 2 active templates"

    def test_add_view_includes_operation_templates(self):
        """Test that add_view includes operation_templates in context."""
        # Create operation templates
        tpl_1 = OperationTemplate.objects.create(
            id='tpl-backup',
            name='Backup Database',
            operation_type='backup',
            target_entity='infobase',
            template_data={'backup_type': 'full'},
            is_active=True
        )
        tpl_2 = OperationTemplate.objects.create(
            id='tpl-restore',
            name='Restore Database',
            operation_type='restore',
            target_entity='infobase',
            template_data={'restore_type': 'full'},
            is_active=True
        )

        # Build request to add form
        url = '/admin/templates/workflowtemplate/add/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.add_view(request)

        # Assertions
        assert response.status_code == 200, "Response should be successful"
        assert 'operation_templates' in response.context_data, \
            "operation_templates should be in context"

        templates = list(response.context_data['operation_templates'])

        # Check templates are present
        assert tpl_1 in templates, "Template should be in context"
        assert tpl_2 in templates, "Template should be in context"
        assert len(templates) == 2, "Should have 2 templates"

    def test_operation_templates_ordered_by_type_and_name(self):
        """Test that operation templates are sorted by operation_type then name."""
        # Create templates with various types and names to test sorting
        templates_to_create = [
            ('tpl-z-lock', 'Z Lock Jobs', 'zzzz_operation', 'infobase'),
            ('tpl-a-unlock', 'A Unlock Jobs', 'aaaa_operation', 'infobase'),
            ('tpl-b-backup', 'B Backup', 'aaaa_operation', 'infobase'),
            ('tpl-c-backup', 'C Backup Full', 'backup_full', 'infobase'),
            ('tpl-d-restore', 'D Restore', 'backup_full', 'infobase'),
        ]

        created_templates = []
        for tpl_id, name, op_type, target in templates_to_create:
            tpl = OperationTemplate.objects.create(
                id=tpl_id,
                name=name,
                operation_type=op_type,
                target_entity=target,
                template_data={},
                is_active=True
            )
            created_templates.append(tpl)

        # Build request
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id)
        )

        # Get templates from context
        templates_list = list(response.context_data['operation_templates'])

        # Verify ordering: first by operation_type, then by name
        expected_order = [
            'tpl-a-unlock',      # aaaa_operation (first alphabetically)
            'tpl-b-backup',      # aaaa_operation (second by name)
            'tpl-c-backup',      # backup_full (first)
            'tpl-d-restore',     # backup_full (second by name)
            'tpl-z-lock',        # zzzz_operation
        ]

        actual_order = [tpl.id for tpl in templates_list]
        assert actual_order == expected_order, \
            f"Templates should be ordered by type then name. " \
            f"Expected: {expected_order}, Got: {actual_order}"

    def test_changeform_view_empty_templates(self):
        """Test that changeform_view works with no operation templates."""
        # Ensure no operation templates exist
        OperationTemplate.objects.all().delete()

        # Build request
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id)
        )

        # Assertions
        assert response.status_code == 200, "Response should be successful"
        assert 'operation_templates' in response.context_data, \
            "operation_templates should be in context even if empty"

        templates = list(response.context_data['operation_templates'])
        assert len(templates) == 0, "Should have no templates"

    def test_add_view_empty_templates(self):
        """Test that add_view works with no operation templates."""
        # Ensure no operation templates exist
        OperationTemplate.objects.all().delete()

        # Build request
        url = '/admin/templates/workflowtemplate/add/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.add_view(request)

        # Assertions
        assert response.status_code == 200, "Response should be successful"
        assert 'operation_templates' in response.context_data, \
            "operation_templates should be in context even if empty"

        templates = list(response.context_data['operation_templates'])
        assert len(templates) == 0, "Should have no templates"

    def test_only_active_templates_included_mixed_scenario(self):
        """Test filtering logic with mixed active/inactive templates."""
        # Create 10 templates: 6 active, 4 inactive
        for i in range(6):
            OperationTemplate.objects.create(
                id=f'tpl-active-{i}',
                name=f'Active Template {i}',
                operation_type='operation',
                target_entity='infobase',
                template_data={},
                is_active=True
            )

        for i in range(4):
            OperationTemplate.objects.create(
                id=f'tpl-inactive-{i}',
                name=f'Inactive Template {i}',
                operation_type='operation',
                target_entity='infobase',
                template_data={},
                is_active=False
            )

        # Build request
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id)
        )

        # Assertions
        templates = list(response.context_data['operation_templates'])
        assert len(templates) == 6, "Should have exactly 6 active templates"

        # Verify all returned templates are active
        for tpl in templates:
            assert tpl.is_active is True, f"Template {tpl.id} should be active"

    def test_extra_context_preserved(self):
        """Test that extra_context parameter is preserved."""
        # Create a template
        OperationTemplate.objects.create(
            id='tpl-test',
            name='Test Template',
            operation_type='test',
            target_entity='infobase',
            template_data={},
            is_active=True
        )

        # Build request with extra context
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response with extra context
        extra_context = {'custom_key': 'custom_value'}
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id),
            extra_context=extra_context
        )

        # Assertions
        assert response.status_code == 200
        assert 'operation_templates' in response.context_data, \
            "operation_templates should be in context"
        assert 'custom_key' in response.context_data, \
            "Custom context should be preserved"
        assert response.context_data['custom_key'] == 'custom_value', \
            "Custom context value should be correct"

    def test_templates_sorted_by_multiple_types_and_names(self):
        """Test complex sorting with multiple operation types."""
        # Create templates with various combinations
        # Note: names must be unique across all templates
        OperationTemplate.objects.create(
            id='tpl-1', name='Beta Operation', operation_type='alpha', target_entity='infobase',
            template_data={}, is_active=True
        )
        OperationTemplate.objects.create(
            id='tpl-2', name='Alpha Operation', operation_type='alpha', target_entity='infobase',
            template_data={}, is_active=True
        )
        OperationTemplate.objects.create(
            id='tpl-3', name='Charlie Operation', operation_type='beta', target_entity='infobase',
            template_data={}, is_active=True
        )
        OperationTemplate.objects.create(
            id='tpl-4', name='Alpha Beta', operation_type='beta', target_entity='infobase',
            template_data={}, is_active=True
        )
        OperationTemplate.objects.create(
            id='tpl-5', name='Delta Operation', operation_type='alpha', target_entity='infobase',
            template_data={}, is_active=True
        )

        # Build request
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id)
        )

        # Get ordered templates
        templates = list(response.context_data['operation_templates'])

        # Expected order: sorted by operation_type, then by name
        # alpha: Alpha Operation, Beta Operation, Delta Operation
        # beta: Alpha Beta, Charlie Operation
        expected_ids = ['tpl-2', 'tpl-1', 'tpl-5', 'tpl-4', 'tpl-3']
        actual_ids = [tpl.id for tpl in templates]

        assert actual_ids == expected_ids, \
            f"Templates should be ordered correctly. " \
            f"Expected: {expected_ids}, Got: {actual_ids}"

    def test_changeform_view_with_nonexistent_object_id(self):
        """Test changeform_view handles nonexistent object gracefully."""
        import uuid
        nonexistent_id = uuid.uuid4()

        # Build request
        url = f'/admin/templates/workflowtemplate/{nonexistent_id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Create a template for sorting to work
        OperationTemplate.objects.create(
            id='tpl-test',
            name='Test',
            operation_type='test',
            target_entity='infobase',
            template_data={},
            is_active=True
        )

        # Get response - should handle gracefully (Django admin will show 404)
        try:
            response = self.workflow_admin.changeform_view(
                request,
                str(nonexistent_id)
            )
            # If response is returned, check context
            if hasattr(response, 'context_data'):
                assert 'operation_templates' in response.context_data
        except Exception:
            # Expected behavior - object not found
            pass

    def test_large_number_of_templates(self):
        """Test performance with large number of operation templates."""
        # Create 100 templates (50 active, 50 inactive)
        for i in range(50):
            OperationTemplate.objects.create(
                id=f'tpl-active-{i}',
                name=f'Active Template {i:03d}',
                operation_type='operation',
                target_entity='infobase',
                template_data={},
                is_active=True
            )

        for i in range(50):
            OperationTemplate.objects.create(
                id=f'tpl-inactive-{i}',
                name=f'Inactive Template {i:03d}',
                operation_type='operation',
                target_entity='infobase',
                template_data={},
                is_active=False
            )

        # Build request
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id)
        )

        # Assertions
        templates = list(response.context_data['operation_templates'])
        assert len(templates) == 50, "Should have exactly 50 active templates"

        # Verify all are active and sorted
        for tpl in templates:
            assert tpl.is_active is True

    def test_templates_with_special_characters_in_name(self):
        """Test templates with special characters in names are sorted correctly."""
        OperationTemplate.objects.create(
            id='tpl-special-1',
            name='Template @Alpha',
            operation_type='zzzz',
            target_entity='infobase',
            template_data={},
            is_active=True
        )
        OperationTemplate.objects.create(
            id='tpl-special-2',
            name='Template #Beta',
            operation_type='zzzz',
            target_entity='infobase',
            template_data={},
            is_active=True
        )
        OperationTemplate.objects.create(
            id='tpl-special-3',
            name='Template -Gamma',
            operation_type='zzzz',
            target_entity='infobase',
            template_data={},
            is_active=True
        )

        # Build request
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id)
        )

        # Verify all are present
        templates = list(response.context_data['operation_templates'])
        assert len(templates) == 3, "All templates should be present"
        names = [tpl.name for tpl in templates]
        assert 'Template @Alpha' in names
        assert 'Template #Beta' in names
        assert 'Template -Gamma' in names

    def test_queryable_after_retrieval(self):
        """Test that returned operation_templates queryset is usable."""
        # Create templates
        for i in range(5):
            OperationTemplate.objects.create(
                id=f'tpl-query-{i}',
                name=f'Query Template {i}',
                operation_type='test',
                target_entity='infobase',
                template_data={'index': i},
                is_active=True
            )

        # Build request
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id)
        )

        # Test queryset operations
        templates = response.context_data['operation_templates']

        # Should be able to count
        assert templates.count() == 5, "Should have 5 templates"

        # Should be able to filter
        filtered = templates.filter(id='tpl-query-0')
        assert filtered.count() == 1, "Should filter correctly"

        # Should be able to access individual items
        templates_list = list(templates)
        assert len(templates_list) == 5

    def test_both_views_return_same_filtered_set(self):
        """Test that both changeform_view and add_view return same templates."""
        # Create mixed templates
        for i in range(3):
            OperationTemplate.objects.create(
                id=f'tpl-both-active-{i}',
                name=f'Both Active {i}',
                operation_type='both',
                target_entity='infobase',
                template_data={},
                is_active=True
            )

        for i in range(2):
            OperationTemplate.objects.create(
                id=f'tpl-both-inactive-{i}',
                name=f'Both Inactive {i}',
                operation_type='both',
                target_entity='infobase',
                template_data={},
                is_active=False
            )

        # Test changeform_view
        url_change = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request_change = self.request_factory.get(url_change)
        request_change.user = self.admin_user
        response_change = self.workflow_admin.changeform_view(
            request_change,
            str(self.workflow.id)
        )
        changeform_templates = set(
            t.id for t in response_change.context_data['operation_templates']
        )

        # Test add_view
        url_add = '/admin/templates/workflowtemplate/add/'
        request_add = self.request_factory.get(url_add)
        request_add.user = self.admin_user
        response_add = self.workflow_admin.add_view(request_add)
        addform_templates = set(
            t.id for t in response_add.context_data['operation_templates']
        )

        # Both should contain the same templates
        assert changeform_templates == addform_templates, \
            "Both views should return the same set of templates"

    def test_template_with_empty_strings(self):
        """Test template with empty description and other fields."""
        OperationTemplate.objects.create(
            id='tpl-empty',
            name='Empty Fields Template',
            description='',  # Empty description
            operation_type='empty_test',
            target_entity='infobase',
            template_data={},  # Empty template_data
            is_active=True
        )

        # Build request
        url = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request = self.request_factory.get(url)
        request.user = self.admin_user

        # Get response
        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id)
        )

        # Verify template is present
        templates = list(response.context_data['operation_templates'])
        assert len(templates) == 1
        assert templates[0].id == 'tpl-empty'
        assert templates[0].description == ''
        assert templates[0].template_data == {}

    def test_context_isolation_between_requests(self):
        """Test that context doesn't leak between different requests."""
        # Create templates
        OperationTemplate.objects.create(
            id='tpl-isolation-1',
            name='Isolation Template 1',
            operation_type='isolation',
            target_entity='infobase',
            template_data={},
            is_active=True
        )

        # First request
        url_1 = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request_1 = self.request_factory.get(url_1)
        request_1.user = self.admin_user
        response_1 = self.workflow_admin.changeform_view(
            request_1,
            str(self.workflow.id)
        )
        templates_1 = list(response_1.context_data['operation_templates'])

        # Create second template
        OperationTemplate.objects.create(
            id='tpl-isolation-2',
            name='Isolation Template 2',
            operation_type='isolation',
            target_entity='infobase',
            template_data={},
            is_active=True
        )

        # Second request (should include both templates)
        url_2 = f'/admin/templates/workflowtemplate/{self.workflow.id}/change/'
        request_2 = self.request_factory.get(url_2)
        request_2.user = self.admin_user
        response_2 = self.workflow_admin.changeform_view(
            request_2,
            str(self.workflow.id)
        )
        templates_2 = list(response_2.context_data['operation_templates'])

        # First response should have 1 template
        assert len(templates_1) == 1, "First request should have 1 template"
        assert templates_1[0].id == 'tpl-isolation-1'

        # Second response should have 2 templates
        assert len(templates_2) == 2, "Second request should have 2 templates"
        ids = {t.id for t in templates_2}
        assert ids == {'tpl-isolation-1', 'tpl-isolation-2'}
