"""
Unit tests for Templates API endpoints (Phase 5.1 - Operations Center).

Tests:
- GET /api/v2/workflows/list-templates/ - list workflow templates
- GET /api/v2/workflows/get-template-schema/ - get template schema
"""

import pytest
import uuid

from rest_framework import status
from django.contrib.auth import get_user_model

from apps.templates.workflow.models import WorkflowTemplate


User = get_user_model()


@pytest.fixture
def workflow_template_ras(db, admin_user):
    """Create RAS category workflow template."""
    return WorkflowTemplate.objects.create(
        name="RAS Template",
        description="Template for RAS operations",
        workflow_type="ras_operation",
        category="ras",
        icon="PlayCircleOutlined",
        dag_structure={
            "nodes": [
                {
                    "id": "step1",
                    "name": "Connect to RAS",
                    "type": "operation",
                    "template_id": "ras_connect",
                    "config": {}
                }
            ],
            "edges": []
        },
        input_schema={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string", "title": "Cluster ID"},
                "infobase": {"type": "string", "title": "Infobase"},
            },
            "required": ["cluster_id", "infobase"]
        },
        created_by=admin_user,
        is_template=True,
        is_active=True,
        is_valid=True,
    )


@pytest.fixture
def workflow_template_odata(db, admin_user):
    """Create OData category workflow template."""
    return WorkflowTemplate.objects.create(
        name="OData Template",
        description="Template for OData operations",
        workflow_type="odata_operation",
        category="odata",
        icon="DatabaseOutlined",
        dag_structure={
            "nodes": [
                {
                    "id": "step1",
                    "name": "OData Query",
                    "type": "operation",
                    "template_id": "odata_query",
                    "config": {}
                }
            ],
            "edges": []
        },
        input_schema={
            "type": "object",
            "properties": {
                "database_id": {"type": "string", "title": "Database ID"},
                "entity": {"type": "string", "title": "Entity Name"},
            },
            "required": ["database_id", "entity"]
        },
        created_by=admin_user,
        is_template=True,
        is_active=True,
        is_valid=True,
    )


@pytest.fixture
def workflow_template_system(db, admin_user):
    """Create system category workflow template."""
    return WorkflowTemplate.objects.create(
        name="System Template",
        description="Template for system operations",
        workflow_type="system_operation",
        category="system",
        icon="SettingOutlined",
        dag_structure={
            "nodes": [
                {
                    "id": "step1",
                    "name": "System Check",
                    "type": "operation",
                    "template_id": "system_check",
                    "config": {}
                }
            ],
            "edges": []
        },
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "title": "Action"},
            },
            "required": ["action"]
        },
        created_by=admin_user,
        is_template=True,
        is_active=True,
        is_valid=True,
    )


@pytest.fixture
def workflow_template_inactive(db, admin_user):
    """Create inactive workflow template."""
    return WorkflowTemplate.objects.create(
        name="Inactive Template",
        description="Inactive template",
        workflow_type="general",
        category="custom",
        dag_structure={
            "nodes": [{"id": "dummy", "name": "Dummy", "type": "operation", "template_id": "dummy"}],
            "edges": []
        },
        created_by=admin_user,
        is_template=True,
        is_active=False,  # Inactive
        is_valid=True,
    )


@pytest.fixture
def workflow_template_invalid(db, admin_user):
    """Create invalid workflow template."""
    return WorkflowTemplate.objects.create(
        name="Invalid Template",
        description="Invalid template",
        workflow_type="general",
        category="custom",
        dag_structure={
            "nodes": [{"id": "dummy", "name": "Dummy", "type": "operation", "template_id": "dummy"}],
            "edges": []
        },
        created_by=admin_user,
        is_template=True,
        is_active=True,
        is_valid=False,  # Invalid
    )


@pytest.fixture
def workflow_not_template(db, admin_user):
    """Create workflow that is not a template."""
    return WorkflowTemplate.objects.create(
        name="Regular Workflow",
        description="Not a template",
        workflow_type="general",
        dag_structure={
            "nodes": [{"id": "dummy", "name": "Dummy", "type": "operation", "template_id": "dummy"}],
            "edges": []
        },
        created_by=admin_user,
        is_template=False,  # Not a template
        is_active=True,
        is_valid=True,
    )


@pytest.mark.django_db
class TestListTemplatesAPI:
    """Test GET /api/v2/workflows/list-templates/ endpoint."""

    def test_list_templates_returns_only_templates(
        self,
        authenticated_client,
        workflow_template_ras,
        workflow_not_template
    ):
        """Test list_templates returns only templates (is_template=True)."""
        url = '/api/v2/workflows/list-templates/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'templates' in response.data
        assert response.data['count'] == 1

        # Should return template, not regular workflow
        template_ids = [t['id'] for t in response.data['templates']]
        assert workflow_template_ras.id in template_ids
        assert workflow_not_template.id not in template_ids

    def test_list_templates_filters_inactive(
        self,
        authenticated_client,
        workflow_template_ras,
        workflow_template_inactive
    ):
        """Test list_templates filters out inactive templates."""
        url = '/api/v2/workflows/list-templates/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

        # Should only return active template
        template_ids = [t['id'] for t in response.data['templates']]
        assert workflow_template_ras.id in template_ids
        assert workflow_template_inactive.id not in template_ids

    def test_list_templates_filters_invalid(
        self,
        authenticated_client,
        workflow_template_ras,
        workflow_template_invalid
    ):
        """Test list_templates filters out invalid templates."""
        url = '/api/v2/workflows/list-templates/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

        # Should only return valid template
        template_ids = [t['id'] for t in response.data['templates']]
        assert workflow_template_ras.id in template_ids
        assert workflow_template_invalid.id not in template_ids

    def test_list_templates_filter_by_category(
        self,
        authenticated_client,
        workflow_template_ras,
        workflow_template_odata,
        workflow_template_system
    ):
        """Test list_templates filters by category."""
        url = '/api/v2/workflows/list-templates/?category=ras'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

        templates = response.data['templates']
        assert templates[0]['id'] == workflow_template_ras.id
        assert templates[0]['category'] == 'ras'

    def test_list_templates_search_by_name(
        self,
        authenticated_client,
        workflow_template_ras,
        workflow_template_odata
    ):
        """Test list_templates searches by name."""
        url = '/api/v2/workflows/list-templates/?search=RAS'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

        templates = response.data['templates']
        assert templates[0]['id'] == workflow_template_ras.id
        assert 'RAS' in templates[0]['name']

    def test_list_templates_search_by_description(
        self,
        authenticated_client,
        workflow_template_ras,
        workflow_template_odata
    ):
        """Test list_templates searches by description."""
        url = '/api/v2/workflows/list-templates/?search=OData'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

        templates = response.data['templates']
        # UUID is returned as UUID object, not string
        assert templates[0]['id'] == workflow_template_odata.id
        assert 'OData' in templates[0]['description']

    def test_list_templates_ordering(
        self,
        authenticated_client,
        workflow_template_ras,
        workflow_template_odata,
        workflow_template_system
    ):
        """Test list_templates ordering by category, name."""
        url = '/api/v2/workflows/list-templates/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 3

        templates = response.data['templates']
        categories = [t['category'] for t in templates]

        # Should be ordered by category first
        assert categories == sorted(categories)

    def test_list_templates_response_structure(
        self,
        authenticated_client,
        workflow_template_ras
    ):
        """Test list_templates response has correct structure."""
        url = '/api/v2/workflows/list-templates/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'templates' in response.data
        assert 'count' in response.data

        template = response.data['templates'][0]
        assert 'id' in template
        assert 'name' in template
        assert 'description' in template
        assert 'category' in template
        assert 'icon' in template
        assert 'workflow_type' in template
        assert 'version_number' in template
        assert 'created_at' in template

    def test_list_templates_unauthenticated(self, api_client, workflow_template_ras):
        """Test list_templates without authentication returns 401."""
        url = '/api/v2/workflows/list-templates/'

        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_templates_empty(self, authenticated_client, db):
        """Test list_templates with no templates returns empty list."""
        url = '/api/v2/workflows/list-templates/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['templates'] == []


@pytest.mark.django_db
class TestGetTemplateSchemaAPI:
    """Test GET /api/v2/workflows/get-template-schema/ endpoint."""

    def test_get_template_schema_success(
        self,
        authenticated_client,
        workflow_template_ras
    ):
        """Test get_template_schema returns correct schema."""
        url = f'/api/v2/workflows/get-template-schema/?workflow_id={workflow_template_ras.id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['workflow_id'] == str(workflow_template_ras.id)
        assert response.data['name'] == workflow_template_ras.name
        assert response.data['description'] == workflow_template_ras.description
        assert response.data['category'] == workflow_template_ras.category
        assert response.data['icon'] == workflow_template_ras.icon
        assert response.data['input_schema'] == workflow_template_ras.input_schema

    def test_get_template_schema_missing_workflow_id(self, authenticated_client):
        """Test get_template_schema without workflow_id returns 400."""
        url = '/api/v2/workflows/get-template-schema/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'MISSING_PARAMETER'
        assert 'workflow_id' in response.data['error']['message']

    def test_get_template_schema_invalid_uuid(self, authenticated_client):
        """Test get_template_schema with invalid UUID returns 400."""
        url = '/api/v2/workflows/get-template-schema/?workflow_id=not-a-uuid'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'INVALID_UUID'

    def test_get_template_schema_not_found(self, authenticated_client):
        """Test get_template_schema with non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        url = f'/api/v2/workflows/get-template-schema/?workflow_id={fake_id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['error']['code'] == 'TEMPLATE_NOT_FOUND'

    def test_get_template_schema_not_template(
        self,
        authenticated_client,
        workflow_not_template
    ):
        """Test get_template_schema for non-template workflow returns 404."""
        url = f'/api/v2/workflows/get-template-schema/?workflow_id={workflow_not_template.id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['error']['code'] == 'TEMPLATE_NOT_FOUND'

    def test_get_template_schema_inactive(
        self,
        authenticated_client,
        workflow_template_inactive
    ):
        """Test get_template_schema for inactive template returns 404."""
        url = f'/api/v2/workflows/get-template-schema/?workflow_id={workflow_template_inactive.id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['error']['code'] == 'TEMPLATE_NOT_FOUND'

    def test_get_template_schema_unauthenticated(
        self,
        api_client,
        workflow_template_ras
    ):
        """Test get_template_schema without authentication returns 401."""
        url = f'/api/v2/workflows/get-template-schema/?workflow_id={workflow_template_ras.id}'

        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_template_schema_with_null_input_schema(
        self,
        authenticated_client,
        admin_user
    ):
        """Test get_template_schema with null input_schema returns correctly."""
        template = WorkflowTemplate.objects.create(
            name="No Schema Template",
            description="Template without input schema",
            workflow_type="general",
            category="custom",
            icon="FileOutlined",
            dag_structure={
                "nodes": [{"id": "dummy", "name": "Dummy", "type": "operation", "template_id": "dummy"}],
                "edges": []
            },
            input_schema=None,  # No schema
            created_by=admin_user,
            is_template=True,
            is_active=True,
            is_valid=True,
        )

        url = f'/api/v2/workflows/get-template-schema/?workflow_id={template.id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['input_schema'] is None

    def test_get_template_schema_response_structure(
        self,
        authenticated_client,
        workflow_template_ras
    ):
        """Test get_template_schema response has all required fields."""
        url = f'/api/v2/workflows/get-template-schema/?workflow_id={workflow_template_ras.id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        # Verify all required fields
        required_fields = ['workflow_id', 'name', 'description', 'category', 'icon', 'input_schema']
        for field in required_fields:
            assert field in response.data

    def test_get_template_schema_input_schema_structure(
        self,
        authenticated_client,
        workflow_template_ras
    ):
        """Test get_template_schema returns valid JSON Schema."""
        url = f'/api/v2/workflows/get-template-schema/?workflow_id={workflow_template_ras.id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        schema = response.data['input_schema']
        assert schema['type'] == 'object'
        assert 'properties' in schema
        assert 'required' in schema

        # Verify properties
        assert 'cluster_id' in schema['properties']
        assert 'infobase' in schema['properties']
        assert 'cluster_id' in schema['required']
