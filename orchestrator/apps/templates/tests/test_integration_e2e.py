"""
End-to-end integration tests for Template Engine.

Tests full flow: Django model → Template rendering → Celery task
"""

import pytest
from apps.templates.models import OperationTemplate
from apps.operations.models import BatchOperation
from apps.templates.engine import TemplateRenderer


@pytest.mark.django_db
class TestEndToEndTemplateFlow:
    """Test complete template flow with Django models."""

    def test_create_template_and_render(self):
        """Test creating template in DB and rendering it."""
        # 1. Create template in database
        template = OperationTemplate.objects.create(
            name='E2E Create User',
            operation_type='create',
            target_entity='Catalog_Users',
            template_data={
                "Name": "{{user_name}}",
                "Email": "{{email}}",
                "ID": "{{user_id|guid1c}}",
                "CreatedAt": "{{current_timestamp|datetime1c}}"
            }
        )

        # 2. Render template
        renderer = TemplateRenderer()
        result = renderer.render(template, {
            "user_name": "Test User",
            "email": "test@example.com",
            "user_id": "12345678-1234-1234-1234-123456789012",
            "current_timestamp": "2025-11-09T15:30:00"
        })

        # 3. Verify result
        assert result['Name'] == "Test User"
        assert result['Email'] == "test@example.com"
        assert result['ID'] == "guid'12345678-1234-1234-1234-123456789012'"
        assert 'datetime' in result['CreatedAt']

        # Cleanup
        template.delete()

    def test_template_with_conditional_logic_e2e(self):
        """Test template with {% if %} conditional logic."""
        template = OperationTemplate.objects.create(
            name='E2E Conditional',
            operation_type='create',
            target_entity='Test',
            template_data={
                "IsActive": "{% if is_production %}true{% else %}false{% endif %}",
                "Permissions": "{% if is_admin %}admin{% else %}user{% endif %}"
            }
        )

        renderer = TemplateRenderer()

        # Test production + admin
        result = renderer.render(template, {"is_production": True, "is_admin": True})
        assert result['IsActive'] == "true"
        assert result['Permissions'] == "admin"

        # Test non-production + regular user
        result = renderer.render(template, {"is_production": False, "is_admin": False})
        assert result['IsActive'] == "false"
        assert result['Permissions'] == "user"

        template.delete()

    def test_template_validation_in_database(self):
        """Test that validator works with database models."""
        from apps.templates.engine import TemplateValidator

        # Create VALID template
        template = OperationTemplate.objects.create(
            name='Valid Template',
            operation_type='create',
            target_entity='Test',
            template_data={"name": "{{user_name}}"}
        )

        validator = TemplateValidator()

        # Should NOT raise validation error
        validator.validate_template(template)

        template.delete()

    def test_template_with_filters_e2e(self):
        """Test template with 1C-specific filters."""
        template = OperationTemplate.objects.create(
            name='E2E Filters',
            operation_type='create',
            target_entity='Test',
            template_data={
                "GUID": "{{id|guid1c}}",
                "DateTime": "{{timestamp|datetime1c}}",
                "Date": "{{date|date1c}}",
                "Bool": "{{active|bool1c}}"
            }
        )

        renderer = TemplateRenderer()
        result = renderer.render(template, {
            "id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-11-09T15:30:00",
            "date": "2025-11-09",
            "active": True
        })

        assert result['GUID'] == "guid'12345678-1234-1234-1234-123456789012'"
        assert "datetime'2025-11-09T15:30:00'" == result['DateTime']
        assert "datetime'2025-11-09T00:00:00'" == result['Date']
        assert result['Bool'] == "true"

        template.delete()

    def test_template_caching_e2e(self):
        """Test that template caching works in E2E scenario."""
        from apps.templates.engine import TemplateCompiler

        template = OperationTemplate.objects.create(
            name='E2E Cache Test',
            operation_type='create',
            target_entity='Test',
            template_data={"name": "{{user_name}}"}
        )

        renderer = TemplateRenderer()

        # Clear cache
        TemplateCompiler._cache.clear()

        # First render - should cache
        result1 = renderer.render(template, {"user_name": "Alice"})

        # Second render - should use cache
        result2 = renderer.render(template, {"user_name": "Bob"})

        # Results should be different (different context)
        assert result1['name'] == "Alice"
        assert result2['name'] == "Bob"

        # Cache should have the template
        assert len(TemplateCompiler._cache) > 0

        template.delete()


@pytest.mark.django_db
class TestCeleryTaskIntegration:
    """Test Celery task integration with Template Engine."""

    def test_process_operation_with_template_task(self):
        """Test Celery task processes template correctly."""
        from apps.databases.models import Database

        # 1. Create database
        database = Database.objects.create(
            id='test-db-001',
            name='test-db-001',
            host='localhost',
            port=80,
            base_name='test_db',
            odata_url='http://localhost/test_db/odata/standard.odata',
            username='admin',
            password='test_password'
        )

        # 2. Create template
        template = OperationTemplate.objects.create(
            name='Celery Test Template',
            operation_type='create',
            target_entity='Catalog_Users',
            template_data={
                "Name": "{{user_name}}",
                "Database": "{{database_name}}"
            }
        )

        # 3. Create operation
        operation = BatchOperation.objects.create(
            id='test-op-001',
            name='Test Operation',
            operation_type='create',
            template=template,
            payload={"user_name": "Alice"}
        )
        operation.target_databases.add(database)

        # 4. Process operation (call Celery task)
        from apps.operations.tasks import process_operation_with_template

        result = process_operation_with_template(str(operation.id))

        # 5. Verify result
        assert result['status'] == 'success'
        assert result['template_rendered'] is True

        # 6. Verify operation updated
        operation.refresh_from_db()
        assert operation.payload['Name'] == "Alice"
        assert operation.payload['Database'] == "test-db-001"
        assert operation.status == 'completed'

        # Cleanup
        operation.delete()
        template.delete()
        database.delete()

    def test_process_operation_without_template(self):
        """Test Celery task with operation that has no template."""
        from apps.databases.models import Database

        # Create database
        database = Database.objects.create(
            id='test-db-002',
            name='test-db-002',
            host='localhost',
            port=80,
            base_name='test_db',
            odata_url='http://localhost/test_db/odata/standard.odata',
            username='admin',
            password='test_password'
        )

        # Create operation WITHOUT template
        operation = BatchOperation.objects.create(
            id='test-op-002',
            name='Test Operation No Template',
            operation_type='create',
            template=None,  # No template!
            payload={"name": "Bob"}
        )
        operation.target_databases.add(database)

        # Process operation
        from apps.operations.tasks import process_operation_with_template

        result = process_operation_with_template(str(operation.id))

        # Should still succeed
        assert result['status'] == 'success'
        assert result['template_rendered'] is False

        # Payload should remain unchanged
        operation.refresh_from_db()
        assert operation.payload['name'] == "Bob"
        assert operation.status == 'completed'

        # Cleanup
        operation.delete()
        database.delete()

    def test_process_operation_with_invalid_template(self):
        """Test Celery task with invalid template (should fail gracefully)."""
        from apps.databases.models import Database

        # Create database
        database = Database.objects.create(
            id='test-db-003',
            name='test-db-003',
            host='localhost',
            port=80,
            base_name='test_db',
            odata_url='http://localhost/test_db/odata/standard.odata',
            username='admin',
            password='test_password'
        )

        # Create template with INVALID syntax
        template = OperationTemplate.objects.create(
            name='Invalid Template',
            operation_type='create',
            target_entity='Test',
            template_data={
                "Name": "{% if missing_var %}"  # INVALID - no endif!
            }
        )

        # Create operation
        operation = BatchOperation.objects.create(
            id='test-op-003',
            name='Test Invalid Template',
            operation_type='create',
            template=template,
            payload={"user_name": "Charlie"}
        )
        operation.target_databases.add(database)

        # Process operation - should raise exception
        from apps.operations.tasks import process_operation_with_template

        with pytest.raises(Exception):
            process_operation_with_template(str(operation.id))

        # Operation should be marked as failed
        operation.refresh_from_db()
        assert operation.status == 'failed'

        # Cleanup
        operation.delete()
        template.delete()
        database.delete()


@pytest.mark.django_db
class TestTemplateLibraryIntegration:
    """Test Template Library integration."""

    def test_load_template_from_library(self):
        """Test loading pre-built template from library."""
        from apps.templates.library import load_template

        # Load catalog_users template
        template_data = load_template('catalog_users')

        # Verify structure
        assert 'name' in template_data
        assert 'template_data' in template_data
        assert 'required_variables' in template_data

        # Create OperationTemplate from library
        template = OperationTemplate.objects.create(
            name=template_data['name'],
            operation_type=template_data['operation_type'],
            target_entity=template_data['target_entity'],
            template_data=template_data['template_data']
        )

        # Render with example context
        renderer = TemplateRenderer()
        result = renderer.render(template, template_data['example_context'])

        # Should render successfully
        assert 'Code' in result  # Based on catalog_users.json
        assert result['Code'] == 'USER001'

        template.delete()

    def test_get_all_templates_from_library(self):
        """Test loading all templates from library."""
        from apps.templates.library import get_template_library

        all_templates = get_template_library()

        # Should have at least 3 templates
        assert len(all_templates) >= 3
        assert 'catalog_users' in all_templates
        assert 'update_prices' in all_templates
        assert 'document_sales' in all_templates

    def test_update_prices_template_from_library(self):
        """Test update_prices template from library."""
        from apps.templates.library import load_template

        template_data = load_template('update_prices')

        # Create template
        template = OperationTemplate.objects.create(
            name=template_data['name'],
            operation_type=template_data['operation_type'],
            target_entity=template_data['target_entity'],
            template_data=template_data['template_data']
        )

        # Render
        renderer = TemplateRenderer()
        result = renderer.render(template, template_data['example_context'])

        # Verify discount calculation
        assert 'data' in result
        # Numbers are returned as strings from Jinja2 templates
        assert float(result['data']['Price']) == 850.5
        assert float(result['data']['OldPrice']) == 1000.0
        assert float(result['data']['Discount']) == 14.95  # (1000-850.5)/1000*100

        template.delete()

    def test_document_sales_template_from_library(self):
        """Test document_sales template from library."""
        from apps.templates.library import load_template

        template_data = load_template('document_sales')

        # Create template
        template = OperationTemplate.objects.create(
            name=template_data['name'],
            operation_type=template_data['operation_type'],
            target_entity=template_data['target_entity'],
            template_data=template_data['template_data']
        )

        # Render
        renderer = TemplateRenderer()
        result = renderer.render(template, template_data['example_context'])

        # Verify calculations (numbers are returned as strings from Jinja2 templates)
        assert float(result['TotalAmount']) == 15000.0
        assert float(result['VATAmount']) == 3000.0  # 20% VAT
        assert float(result['GrandTotal']) == 18000.0  # Total + VAT

        template.delete()

    def test_library_template_not_found(self):
        """Test loading non-existent template from library."""
        from apps.templates.library import load_template

        with pytest.raises(FileNotFoundError):
            load_template('non_existent_template')
