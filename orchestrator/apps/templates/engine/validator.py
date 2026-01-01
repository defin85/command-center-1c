"""
Template schema validation.

Validates:
- Template structure (required fields)
- Variable syntax ({{var}})
- Conditional syntax ({% if %})
- Security (no dangerous patterns)
"""

import re
import json
from typing import Dict, Any, List
from .exceptions import TemplateValidationError


class TemplateValidator:
    """Validates template schema and security."""

    # Dangerous patterns as strings (for documentation)
    _DANGEROUS_PATTERN_STRINGS = [
        r'__\w+__',           # Dunder attributes (__class__, __globals__, etc.)
        r'\.mro\(',           # Method resolution order
        r'\.subclasses\(',    # Subclasses introspection
        r'exec\s*\(',         # Code execution
        r'eval\s*\(',         # Expression evaluation
        r'import\s+',         # Module imports
        r'__import__',        # Dynamic imports
        r'compile\s*\(',      # Code compilation
        r'open\s*\(',         # File operations
        r'file\s*\(',         # File operations
        r'input\s*\(',        # User input
        r'raw_input\s*\(',    # User input (Python 2)
    ]

    # Valid operation types fallback (used when registry is empty)
    VALID_OPERATION_TYPES = [
        'create',
        'update',
        'delete',
        'batch_create',
        'batch_update',
        'batch_delete',
        'query',
    ]

    def __init__(self):
        """Initialize validator with compiled patterns and cached environment."""
        # Compile regex patterns once (5x faster)
        self.dangerous_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self._DANGEROUS_PATTERN_STRINGS
        ]

        # Create cached Jinja2 environment (10x faster syntax validation)
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        from jinja2 import DictLoader, StrictUndefined
        from .filters import register_custom_filters
        from .tests import register_custom_tests

        self._jinja_env = ImmutableSandboxedEnvironment(
            loader=DictLoader({}),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )

        # Register custom filters and tests
        register_custom_filters(self._jinja_env)
        register_custom_tests(self._jinja_env)

        # Add safe globals
        self._jinja_env.globals.update({
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
        })

    def validate_template(self, template):
        """
        Validate template schema and security.

        Args:
            template: OperationTemplate instance (Django model)

        Raises:
            TemplateValidationError: If validation fails
        """
        errors = []

        # 1. Validate required fields
        errors.extend(self._validate_required_fields(template))

        # 2. Validate template_data is valid JSON
        errors.extend(self._validate_json_syntax(template))

        # 3. Security validation (dangerous patterns)
        errors.extend(self._validate_security(template))

        # 4. Validate Jinja2 syntax
        errors.extend(self._validate_jinja2_syntax(template))

        # 5. Validate business logic
        errors.extend(self._validate_business_logic(template))

        # Raise if any errors
        if errors:
            raise TemplateValidationError(
                f"Template validation failed for '{template.name}': " +
                "; ".join(errors)
            )

    def _validate_required_fields(self, template) -> List[str]:
        """Validate required fields are present."""
        errors = []

        if not template.name:
            errors.append("name is required")

        if not template.operation_type:
            errors.append("operation_type is required")

        if not template.template_data:
            errors.append("template_data is required")

        return errors

    def _validate_json_syntax(self, template) -> List[str]:
        """Validate template_data is valid JSON."""
        errors = []

        try:
            if isinstance(template.template_data, str):
                json.loads(template.template_data)
            elif isinstance(template.template_data, (dict, list)):
                # Already valid (Django JSONField)
                json.dumps(template.template_data)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in template_data: {e}")

        return errors

    def _validate_security(self, template) -> List[str]:
        """Validate template doesn't contain dangerous patterns."""
        errors = []

        # Skip if template_data is None or empty (will be caught by required fields validation)
        if not template.template_data:
            return errors

        # Convert template_data to string for pattern matching
        if isinstance(template.template_data, (dict, list)):
            template_str = json.dumps(template.template_data)
        else:
            template_str = template.template_data

        # Check each dangerous pattern (NOW USING COMPILED PATTERNS!)
        for compiled_pattern in self.dangerous_patterns:
            matches = compiled_pattern.findall(template_str)
            if matches:
                # Get original pattern string for error message
                pattern_str = compiled_pattern.pattern
                errors.append(
                    f"Security violation: dangerous pattern detected: '{pattern_str}' "
                    f"(found: {matches[0]})"
                )

        return errors

    def _validate_jinja2_syntax(self, template) -> List[str]:
        """Validate Jinja2 template syntax."""
        errors = []

        # Skip if template_data is None or empty (will be caught by required fields validation)
        if not template.template_data:
            return errors

        try:
            # Convert to string
            if isinstance(template.template_data, (dict, list)):
                template_str = json.dumps(template.template_data)
            else:
                template_str = template.template_data

            # Try to parse template (NOW USING CACHED ENVIRONMENT!)
            self._jinja_env.from_string(template_str)

        except Exception as e:
            errors.append(f"Invalid Jinja2 syntax: {str(e)}")

        return errors

    def _validate_business_logic(self, template) -> List[str]:
        """Validate business logic rules."""
        errors = []

        # 1. Validate operation_type against registry (fallback to whitelist)
        valid_types = set(self.VALID_OPERATION_TYPES)
        try:
            from apps.templates.registry import get_registry, TargetEntity

            registry = get_registry()
            if registry.get_all():
                valid_types = set(registry.get_ids())
        except Exception:
            registry = None

        if template.operation_type not in valid_types:
            allowed = ", ".join(sorted(valid_types))
            errors.append(
                f"Invalid operation_type: '{template.operation_type}'. "
                f"Allowed: {allowed}"
            )

        # 2. Validate target_entity if operation requires it
        if registry and registry.get_all():
            op = registry.get(template.operation_type)
            if op and op.target_entity == TargetEntity.ENTITY and not template.target_entity:
                errors.append(
                    f"target_entity is required for operation_type '{template.operation_type}'"
                )
        elif template.operation_type in ['create', 'update', 'delete'] and not template.target_entity:
            errors.append(
                f"target_entity is required for operation_type '{template.operation_type}'"
            )

        return errors

    def validate_template_data_only(self, template_data: Dict[str, Any]) -> List[str]:
        """
        Validate only template_data (for REST API preview/validation).

        Args:
            template_data: Template data dict

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # 1. JSON syntax
        try:
            json.dumps(template_data)
        except Exception as e:
            errors.append(f"Invalid JSON: {e}")

        # 2. Security patterns (NOW USING COMPILED PATTERNS!)
        template_str = json.dumps(template_data)
        for compiled_pattern in self.dangerous_patterns:
            matches = compiled_pattern.findall(template_str)
            if matches:
                pattern_str = compiled_pattern.pattern
                errors.append(
                    f"Security violation: '{pattern_str}' (found: {matches[0]})"
                )

        # 3. Jinja2 syntax (NOW USING CACHED ENVIRONMENT!)
        try:
            self._jinja_env.from_string(template_str)
        except Exception as e:
            errors.append(f"Invalid Jinja2 syntax: {e}")

        return errors
