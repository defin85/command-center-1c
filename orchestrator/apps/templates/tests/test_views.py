import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.templates.models import OperationTemplate


@pytest.mark.django_db
class TestOperationTemplateValidateAction(TestCase):
    """Test the /templates/{id}/validate/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.valid_template = OperationTemplate.objects.create(
            id='test-001',
            name='Valid Template',
            operation_type='create',
            target_entity='Catalog_Users',
            template_data={
                "Name": "{{user_name}}",
                "Email": "{{email}}"
            }
        )

    def test_validate_valid_template_returns_200(self):
        """Test that valid template returns 200 OK."""
        response = self.client.post(f'/api/v1/templates/{self.valid_template.id}/validate/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['valid'] is True
        assert 'message' in response.data

    def test_validate_template_with_missing_required_field(self):
        """Test that template with missing required field returns 400."""
        template = OperationTemplate.objects.create(
            id='test-002',
            name='',  # Missing name
            operation_type='create',
            target_entity='Catalog_Users',
            template_data={"test": "data"}
        )

        response = self.client.post(f'/api/v1/templates/{template.id}/validate/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['valid'] is False
        assert 'name is required' in response.data['errors']

    def test_validate_template_with_dangerous_pattern(self):
        """Test that template with dangerous pattern returns 400."""
        template = OperationTemplate.objects.create(
            id='test-003',
            name='Malicious Template',
            operation_type='create',
            target_entity='Catalog_Users',
            template_data={
                "attack": "{{ obj.__class__ }}"
            }
        )

        response = self.client.post(f'/api/v1/templates/{template.id}/validate/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['valid'] is False
        assert 'Security violation' in response.data['errors']

    def test_validate_template_with_invalid_jinja2_syntax(self):
        """Test that template with invalid Jinja2 syntax returns 400."""
        template = OperationTemplate.objects.create(
            id='test-004',
            name='Bad Syntax Template',
            operation_type='create',
            target_entity='Catalog_Users',
            template_data={
                "bad": "{{ unclosed"
            }
        )

        response = self.client.post(f'/api/v1/templates/{template.id}/validate/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['valid'] is False
        assert 'Jinja2 syntax' in response.data['errors']

    def test_validate_template_with_invalid_operation_type(self):
        """Test that template with invalid operation_type returns 400."""
        template = OperationTemplate.objects.create(
            id='test-005',
            name='Invalid Operation',
            operation_type='invalid_op',
            target_entity='Catalog_Users',
            template_data={"test": "data"}
        )

        response = self.client.post(f'/api/v1/templates/{template.id}/validate/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['valid'] is False
        assert 'Invalid operation_type' in response.data['errors']

    def test_validate_template_with_missing_target_entity(self):
        """Test that template with missing target_entity for 'create' returns 400."""
        template = OperationTemplate.objects.create(
            id='test-006',
            name='Missing Target',
            operation_type='create',
            target_entity='',  # Empty
            template_data={"test": "data"}
        )

        response = self.client.post(f'/api/v1/templates/{template.id}/validate/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['valid'] is False
        assert 'target_entity is required' in response.data['errors']


@pytest.mark.django_db
class TestOperationTemplateValidateDataAction(TestCase):
    """Test the /templates/validate_data/ endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_validate_data_with_valid_template_data(self):
        """Test that valid template_data returns 200 OK."""
        data = {
            'template_data': {
                "Name": "{{user_name}}",
                "Email": "{{email}}"
            }
        }

        response = self.client.post('/api/v1/templates/validate_data/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['valid'] is True
        assert response.data['errors'] == []

    def test_validate_data_with_missing_template_data(self):
        """Test that missing template_data returns 400."""
        data = {}

        response = self.client.post('/api/v1/templates/validate_data/', data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['valid'] is False
        assert 'template_data is required' in response.data['errors']

    def test_validate_data_with_dangerous_pattern(self):
        """Test that template_data with dangerous pattern returns 400."""
        data = {
            'template_data': {
                "attack": "{{ obj.__class__ }}"
            }
        }

        response = self.client.post('/api/v1/templates/validate_data/', data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['valid'] is False
        assert any('Security violation' in err for err in response.data['errors'])

    def test_validate_data_with_invalid_jinja2_syntax(self):
        """Test that template_data with invalid Jinja2 syntax returns 400."""
        data = {
            'template_data': {
                "bad": "{{ unclosed"
            }
        }

        response = self.client.post('/api/v1/templates/validate_data/', data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['valid'] is False
        assert any('Jinja2 syntax' in err for err in response.data['errors'])

    def test_validate_data_with_complex_valid_template(self):
        """Test validation of complex valid template_data."""
        data = {
            'template_data': {
                "Code": "{{user_code}}",
                "Description": "{{user_name}}",
                "Email": "{{email}}",
                "IsActive": "{% if is_active %}true{% else %}false{% endif %}",
                "Department": "{{department|default('IT')}}"
            }
        }

        response = self.client.post('/api/v1/templates/validate_data/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['valid'] is True
        assert response.data['errors'] == []

    def test_validate_data_with_multiple_errors(self):
        """Test that multiple errors are collected."""
        data = {
            'template_data': {
                "attack1": "{{ obj.__class__ }}",  # Security violation
                "attack2": "{{ unclosed"  # Syntax error
            }
        }

        response = self.client.post('/api/v1/templates/validate_data/', data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['valid'] is False
        assert len(response.data['errors']) >= 1  # At least one error

    def test_validate_data_with_list_template_data(self):
        """Test validation of list template_data."""
        data = {
            'template_data': ["{{item1}}", "{{item2}}"]
        }

        response = self.client.post('/api/v1/templates/validate_data/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['valid'] is True
        assert response.data['errors'] == []
