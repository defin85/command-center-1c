# Example: DRF ViewSet test pattern
# apps/operations/tests/test_views.py

from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from apps.operations.models import Operation
from django.contrib.auth.models import User


class OperationViewSetTest(APITestCase):
    """Test OperationViewSet CRUD operations"""

    def setUp(self):
        """Setup test data for each test method"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.operation = Operation.objects.create(
            name="Test Operation",
            operation_type="create_users",
            created_by=self.user
        )

    def test_list_operations(self):
        """Test GET /api/operations/ returns list"""
        response = self.client.get('/api/operations/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Operation')

    def test_create_operation(self):
        """Test POST /api/operations/ creates new operation"""
        data = {
            'name': 'New Operation',
            'operation_type': 'update_users',
            'template_id': 1
        }
        response = self.client.post('/api/operations/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Operation.objects.count(), 2)
        self.assertEqual(response.data['name'], 'New Operation')

    def test_retrieve_operation(self):
        """Test GET /api/operations/{id}/ returns single operation"""
        response = self.client.get(f'/api/operations/{self.operation.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Operation')

    def test_update_operation(self):
        """Test PATCH /api/operations/{id}/ updates operation"""
        data = {'name': 'Updated Name'}
        response = self.client.patch(
            f'/api/operations/{self.operation.id}/',
            data
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.name, 'Updated Name')

    def test_delete_operation(self):
        """Test DELETE /api/operations/{id}/ deletes operation"""
        response = self.client.delete(f'/api/operations/{self.operation.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Operation.objects.count(), 0)

    def test_create_operation_validation(self):
        """Test validation errors on create"""
        data = {'name': ''}  # Empty name should fail
        response = self.client.post('/api/operations/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
