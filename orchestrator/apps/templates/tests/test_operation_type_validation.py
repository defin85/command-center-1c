# orchestrator/apps/templates/tests/test_operation_type_validation.py
"""
Tests for OperationTemplate.operation_type validation against registry.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.templates.models import OperationTemplate, validate_operation_type
from apps.templates.registry import get_registry


@pytest.mark.django_db
class TestValidateOperationType:
    def test_valid_operation_type_accepted(self):
        registry = get_registry()
        valid_types = list(registry.get_ids())
        assert len(valid_types) > 0

        for op_type in valid_types:
            try:
                validate_operation_type(op_type)
            except ValidationError:
                pytest.fail(f"Valid operation type '{op_type}' should not raise ValidationError")

    def test_invalid_operation_type_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_operation_type("totally_invalid_operation_type_xyz")

        error_message = str(exc_info.value.message)
        assert "Unknown operation type" in error_message
        assert "totally_invalid_operation_type_xyz" in error_message
        assert "Valid types:" in error_message

    def test_error_message_contains_valid_types(self):
        registry = get_registry()
        valid_types = sorted(registry.get_ids())

        with pytest.raises(ValidationError) as exc_info:
            validate_operation_type("invalid_type")

        error_message = str(exc_info.value.message)
        for valid_type in valid_types:
            assert valid_type in error_message


@pytest.mark.django_db
class TestOperationTemplateModelValidation:
    def test_field_has_validator(self):
        field = OperationTemplate._meta.get_field("operation_type")
        validator_found = False
        for validator in field.validators:
            if hasattr(validator, "__name__") and validator.__name__ == "validate_operation_type":
                validator_found = True
                break
            if callable(validator) and validator.__name__ == "validate_operation_type":
                validator_found = True
                break

        assert validator_found


@pytest.mark.django_db
class TestRegistryIntegration:
    def test_registry_has_registered_operations(self):
        registry = get_registry()
        operations = registry.get_all()
        assert len(operations) > 0

    def test_registry_choices_match_validation(self):
        registry = get_registry()
        choices = registry.get_choices()

        for choice_id, _choice_label in choices:
            try:
                validate_operation_type(choice_id)
            except ValidationError:
                pytest.fail(f"Registry choice '{choice_id}' should pass validation")

    def test_registry_includes_ras_operations(self):
        from apps.templates.registry import BackendType

        registry = get_registry()
        ras_ops = registry.get_by_backend(BackendType.RAS)
        assert len(ras_ops) > 0

        ras_ids = {op.id for op in ras_ops}
        expected_ras_ops = {"lock_scheduled_jobs", "unlock_scheduled_jobs"}
        assert expected_ras_ops.issubset(ras_ids)

    def test_registry_includes_odata_operations(self):
        from apps.templates.registry import BackendType

        registry = get_registry()
        odata_ops = registry.get_by_backend(BackendType.ODATA)
        assert len(odata_ops) > 0

        odata_ids = {op.id for op in odata_ops}
        expected_odata_ops = {"create", "update", "delete", "query"}
        assert expected_odata_ops.issubset(odata_ids)
