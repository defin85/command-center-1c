# orchestrator/apps/templates/tests/test_operation_type_validation.py
"""
Tests for OperationTemplate.operation_type validation against registry.

Tests verify:
- Valid operation types are accepted
- Invalid operation types are rejected with proper error message
- Field-level validator is applied during full_clean()
- Admin form uses dynamic choices from registry
- Validation gracefully handles empty registry
"""

import pytest
from django.core.exceptions import ValidationError
from django.contrib.admin.sites import AdminSite

from apps.templates.models import OperationTemplate, validate_operation_type
from apps.templates.admin import (
    OperationTemplateAdmin,
    OperationTemplateAdminForm,
    get_operation_type_choices,
)
from apps.templates.registry import get_registry


@pytest.mark.django_db
class TestValidateOperationType:
    """Tests for validate_operation_type validator function."""

    def test_valid_operation_type_accepted(self):
        """Test that registered operation types pass validation."""
        registry = get_registry()
        valid_types = list(registry.get_ids())

        # Ensure we have some registered types
        assert len(valid_types) > 0, "Registry should have registered types"

        # Each valid type should pass without raising exception
        for op_type in valid_types:
            try:
                validate_operation_type(op_type)
            except ValidationError:
                pytest.fail(f"Valid operation type '{op_type}' should not raise ValidationError")

    def test_invalid_operation_type_rejected(self):
        """Test that unregistered operation types are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_operation_type('totally_invalid_operation_type_xyz')

        error_message = str(exc_info.value.message)
        assert "Unknown operation type" in error_message
        assert "totally_invalid_operation_type_xyz" in error_message
        assert "Valid types:" in error_message

    def test_error_message_contains_valid_types(self):
        """Test that error message lists all valid operation types."""
        registry = get_registry()
        valid_types = sorted(registry.get_ids())

        with pytest.raises(ValidationError) as exc_info:
            validate_operation_type('invalid_type')

        error_message = str(exc_info.value.message)

        # Check that valid types are mentioned in error
        for valid_type in valid_types:
            assert valid_type in error_message, \
                f"Error message should contain valid type '{valid_type}'"

    def test_lock_scheduled_jobs_is_valid(self):
        """Test specific known operation type: lock_scheduled_jobs."""
        # This is a RAS operation that should be registered
        try:
            validate_operation_type('lock_scheduled_jobs')
        except ValidationError:
            pytest.fail("'lock_scheduled_jobs' should be a valid operation type")

    def test_create_odata_operation_is_valid(self):
        """Test specific known operation type: create (OData)."""
        # This is an OData operation that should be registered
        try:
            validate_operation_type('create')
        except ValidationError:
            pytest.fail("'create' should be a valid operation type")


@pytest.mark.django_db
class TestOperationTemplateModelValidation:
    """Tests for OperationTemplate model validation."""

    def test_full_clean_validates_operation_type(self):
        """Test that model full_clean() validates operation_type via field validator."""
        template = OperationTemplate(
            id='test-invalid-template',
            name='Test Invalid Template',
            operation_type='completely_invalid_type',
            target_entity='infobase',
        )

        with pytest.raises(ValidationError) as exc_info:
            template.full_clean()

        # Check error is on operation_type field
        assert 'operation_type' in exc_info.value.message_dict

    def test_full_clean_accepts_valid_operation_type(self):
        """Test that model full_clean() accepts valid operation_type."""
        template = OperationTemplate(
            id='test-valid-template',
            name='Test Valid Template',
            operation_type='lock_scheduled_jobs',  # Valid RAS operation
            target_entity='infobase',
        )

        # Should not raise (no validation error for operation_type)
        try:
            template.full_clean()
        except ValidationError as e:
            # If there's an error, it shouldn't be about operation_type
            if 'operation_type' in e.message_dict:
                pytest.fail("Valid operation_type should not raise ValidationError")

    def test_field_has_validator(self):
        """Test that operation_type field has the validator attached."""
        field = OperationTemplate._meta.get_field('operation_type')

        # Find our validator in the list
        validator_found = False
        for validator in field.validators:
            if hasattr(validator, '__name__') and validator.__name__ == 'validate_operation_type':
                validator_found = True
                break
            if callable(validator) and validator.__name__ == 'validate_operation_type':
                validator_found = True
                break

        assert validator_found, \
            "operation_type field should have validate_operation_type validator"


@pytest.mark.django_db
class TestOperationTemplateAdminForm:
    """Tests for OperationTemplateAdminForm with dynamic choices."""

    def test_get_operation_type_choices_returns_registry_choices(self):
        """Test that get_operation_type_choices returns choices from registry."""
        choices = get_operation_type_choices()

        # Should have choices
        assert len(choices) > 0, "Should return operation type choices"

        # Each choice should be a tuple (id, label)
        for choice in choices:
            assert isinstance(choice, tuple), "Choice should be a tuple"
            assert len(choice) == 2, "Choice should be (id, label)"

    def test_form_field_has_select_widget(self):
        """Test that form's operation_type field uses Select widget."""
        from django import forms

        form = OperationTemplateAdminForm()
        widget = form.fields['operation_type'].widget

        assert isinstance(widget, forms.Select), \
            "operation_type should use Select widget"

    def test_form_field_has_choices_from_registry(self):
        """Test that form's operation_type field has choices from registry."""
        form = OperationTemplateAdminForm()
        widget = form.fields['operation_type'].widget

        # Get choices from widget
        choices = list(widget.choices)

        # Should have choices
        assert len(choices) > 0, "Widget should have choices"

        # Check that known operation types are in choices
        choice_ids = [c[0] for c in choices]
        assert 'lock_scheduled_jobs' in choice_ids, \
            "lock_scheduled_jobs should be in choices"

    def test_admin_uses_custom_form(self):
        """Test that OperationTemplateAdmin uses OperationTemplateAdminForm."""
        admin_site = AdminSite()
        admin = OperationTemplateAdmin(OperationTemplate, admin_site)

        assert admin.form == OperationTemplateAdminForm, \
            "Admin should use OperationTemplateAdminForm"


@pytest.mark.django_db
class TestRegistryIntegration:
    """Tests for registry integration with validation."""

    def test_registry_has_registered_operations(self):
        """Test that registry has operations registered."""
        registry = get_registry()
        operations = registry.get_all()

        assert len(operations) > 0, "Registry should have operations"

    def test_registry_choices_match_validation(self):
        """Test that all registry choices pass validation."""
        registry = get_registry()
        choices = registry.get_choices()

        for choice_id, choice_label in choices:
            # Each choice should pass validation
            try:
                validate_operation_type(choice_id)
            except ValidationError:
                pytest.fail(f"Registry choice '{choice_id}' should pass validation")

    def test_registry_includes_ras_operations(self):
        """Test that registry includes RAS operations."""
        from apps.templates.registry import BackendType

        registry = get_registry()
        ras_ops = registry.get_by_backend(BackendType.RAS)

        assert len(ras_ops) > 0, "Registry should have RAS operations"

        # Check for expected RAS operations
        ras_ids = {op.id for op in ras_ops}
        expected_ras_ops = {'lock_scheduled_jobs', 'unlock_scheduled_jobs'}
        assert expected_ras_ops.issubset(ras_ids), \
            f"RAS operations should include {expected_ras_ops}"

    def test_registry_includes_odata_operations(self):
        """Test that registry includes OData operations."""
        from apps.templates.registry import BackendType

        registry = get_registry()
        odata_ops = registry.get_by_backend(BackendType.ODATA)

        assert len(odata_ops) > 0, "Registry should have OData operations"

        # Check for expected OData operations
        odata_ids = {op.id for op in odata_ops}
        expected_odata_ops = {'create', 'update', 'delete', 'query'}
        assert expected_odata_ops.issubset(odata_ids), \
            f"OData operations should include {expected_odata_ops}"
