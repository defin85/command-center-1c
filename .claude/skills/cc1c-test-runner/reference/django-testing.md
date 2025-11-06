# Django Testing Reference

Детальное руководство по тестированию Django приложений в CommandCenter1C.

## Running Django Tests

### Basic Commands

```bash
# All Django tests
cd orchestrator
python manage.py test

# Specific app
python manage.py test apps.operations

# Specific test case
python manage.py test apps.operations.tests.test_views.OperationViewSetTest

# Specific test method
python manage.py test apps.operations.tests.test_views.OperationViewSetTest.test_create_operation

# With coverage (using pytest)
pytest --cov=apps --cov-report=html

# Verbose output
python manage.py test --verbosity=2

# Keep database (for debugging)
python manage.py test --keepdb

# Parallel execution
python manage.py test --parallel

# Failed tests only (pytest)
pytest --lf  # last failed
pytest --ff  # failed first
```

## Test Patterns

### Model Tests

```python
# apps/operations/tests/test_models.py
from django.test import TestCase
from apps.operations.models import Operation

class OperationModelTest(TestCase):
    def setUp(self):
        self.operation = Operation.objects.create(
            name="Test Operation",
            operation_type="create_users",
            status="pending"
        )

    def test_operation_creation(self):
        """Test operation is created correctly"""
        self.assertEqual(Operation.objects.count(), 1)
        self.assertEqual(self.operation.name, "Test Operation")
        self.assertEqual(self.operation.status, "pending")

    def test_str_representation(self):
        """Test string representation"""
        expected = f"Operation {self.operation.id}: Test Operation"
        self.assertEqual(str(self.operation), expected)

    def test_default_status(self):
        """Test default status is pending"""
        op = Operation.objects.create(name="Test")
        self.assertEqual(op.status, "pending")
```

### ViewSet Tests

```python
# apps/operations/tests/test_views.py
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from apps.operations.models import Operation

class OperationViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.operation = Operation.objects.create(
            name="Test Operation",
            operation_type="create_users"
        )

    def test_list_operations(self):
        """Test getting list of operations"""
        response = self.client.get('/api/operations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_operation(self):
        """Test creating new operation"""
        data = {
            'name': 'New Operation',
            'operation_type': 'update_users',
            'template_id': 1
        }
        response = self.client.post('/api/operations/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Operation.objects.count(), 2)

    def test_retrieve_operation(self):
        """Test getting single operation"""
        response = self.client.get(f'/api/operations/{self.operation.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Operation')

    def test_update_operation(self):
        """Test updating operation"""
        data = {'name': 'Updated Name'}
        response = self.client.patch(
            f'/api/operations/{self.operation.id}/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.name, 'Updated Name')
```

### Service Layer Tests

```python
# apps/operations/tests/test_services.py
from django.test import TestCase
from unittest.mock import Mock, patch
from apps.operations.services import OperationService
from apps.operations.models import Operation

class OperationServiceTest(TestCase):
    def setUp(self):
        self.service = OperationService()

    @patch('apps.operations.tasks.process_operation_task.delay')
    def test_create_operation_dispatches_task(self, mock_task):
        """Test that creating operation dispatches Celery task"""
        data = {
            'name': 'Test Operation',
            'operation_type': 'create_users',
            'template_id': 1
        }

        operation = self.service.create_operation(data)

        self.assertIsNotNil(operation)
        mock_task.assert_called_once_with(operation.id)

    def test_validate_operation_data(self):
        """Test operation data validation"""
        invalid_data = {'name': ''}  # Empty name

        with self.assertRaises(ValueError):
            self.service.create_operation(invalid_data)
```

### Celery Task Tests

```python
# apps/operations/tests/test_tasks.py
from django.test import TestCase
from unittest.mock import Mock, patch
from apps.operations.tasks import process_operation_task
from apps.operations.models import Operation

class TasksTest(TestCase):
    def setUp(self):
        self.operation = Operation.objects.create(
            name="Test Operation",
            operation_type="create_users"
        )

    @patch('apps.operations.tasks.WorkerClient')
    def test_process_operation_task(self, mock_worker):
        """Test operation processing task"""
        mock_worker.return_value.process.return_value = {'status': 'success'}

        result = process_operation_task(self.operation.id)

        self.assertEqual(result['status'], 'success')
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.status, 'completed')
```

## Coverage

```bash
# Install coverage
pip install coverage pytest-cov

# Run with coverage
pytest --cov=apps --cov-report=term-missing

# HTML report
pytest --cov=apps --cov-report=html
# Open htmlcov/index.html in browser

# Check specific app
pytest --cov=apps.operations --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=apps --cov-fail-under=70
```

## Best Practices

### 1. Use Fixtures

```python
# conftest.py
import pytest
from apps.operations.models import Operation

@pytest.fixture
def operation():
    return Operation.objects.create(
        name="Test Operation",
        operation_type="create_users"
    )

# In tests
def test_operation(operation):
    assert operation.name == "Test Operation"
```

### 2. Database Transactions

```python
from django.test import TransactionTestCase

class MyTransactionTest(TransactionTestCase):
    # Use when testing transactions
    def test_transaction_handling(self):
        # Test code
        pass
```

### 3. Mocking External Services

```python
@patch('apps.operations.clients.ODataClient')
def test_with_mocked_odata(self, mock_client):
    mock_client.return_value.query.return_value = {'data': []}
    # Test code
```
