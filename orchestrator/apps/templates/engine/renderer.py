"""
Template rendering with Jinja2 ImmutableSandboxedEnvironment.

SECURITY:
- Uses ImmutableSandboxedEnvironment for maximum safety
- Validates template schema before rendering
- Whitelists allowed functions/filters
- Logs all rendering operations for audit
"""

from jinja2.sandbox import ImmutableSandboxedEnvironment
from jinja2 import DictLoader, StrictUndefined
from typing import Dict, Any
import logging
import json
from datetime import datetime, date

from .context import ContextBuilder
from .filters import register_custom_filters
from .tests import register_custom_tests
from .exceptions import TemplateRenderError
from .validator import TemplateValidator
from .compiler import TemplateCompiler

logger = logging.getLogger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


class TemplateRenderer:
    """
    Main facade for template rendering.

    Usage:
        renderer = TemplateRenderer()
        result = renderer.render(template_obj, context_data)
    """

    def __init__(self):
        # Create Jinja2 environment
        self.env = ImmutableSandboxedEnvironment(
            loader=DictLoader({}),
            autoescape=False,  # Disable autoescape - we're rendering JSON/OData, not HTML
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,  # Raise error on undefined variables
        )

        # Register custom filters
        register_custom_filters(self.env)

        # Register custom tests
        register_custom_tests(self.env)

        # Add safe globals (whitelisted functions)
        self.env.globals.update({
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
        })

        # Initialize components
        self.context_builder = ContextBuilder()
        self.validator = TemplateValidator()
        self.compiler = TemplateCompiler(self.env)

    def render(
        self,
        template,  # OperationTemplate Django model
        context_data: Dict[str, Any],
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Render template with context data.

        Args:
            template: OperationTemplate instance
            context_data: Variables for template context
            validate: Whether to validate template before rendering (default: True)

        Returns:
            Rendered template data (dict)

        Raises:
            TemplateValidationError: If validation fails (when validate=True)
            TemplateRenderError: If rendering fails
        """
        try:
            # 1. Validate template schema (if enabled)
            if validate:
                self.validator.validate_template(template)

            # 2. Build safe context
            context = self.context_builder.build_context(
                template=template,
                data=context_data
            )

            # 3. Recursively render template_data
            result = self._render_recursive(template.template_data, context)

            # 4. Log rendering
            logger.info(
                "Template rendered successfully",
                extra={
                    'template_id': str(template.id),
                    'template_name': template.name,
                    'context_keys': list(context.keys())
                }
            )

            return result

        except Exception as exc:
            logger.error(
                f"Template rendering failed: {exc}",
                extra={
                    'template_id': str(template.id),
                    'error': str(exc)
                },
                exc_info=True
            )
            raise TemplateRenderError(
                f"Failed to render template {template.name}: {exc}"
            ) from exc

    def _render_recursive(self, data: Any, context: Dict[str, Any]) -> Any:
        """
        Recursively render template data preserving types.

        Args:
            data: Template data (dict, list, str, int, etc.)
            context: Rendering context

        Returns:
            Rendered data with preserved types
        """
        if isinstance(data, dict):
            # Recursively render dictionary values
            return {key: self._render_recursive(value, context) for key, value in data.items()}
        elif isinstance(data, list):
            # Recursively render list items
            return [self._render_recursive(item, context) for item in data]
        elif isinstance(data, str):
            # Render string as Jinja2 template (with caching)
            # Use data itself as template_id for caching individual strings
            # Generate a simple hash-based ID for string templates
            import hashlib
            template_id = f"str_{hashlib.md5(data.encode()).hexdigest()[:8]}"
            compiled = self.compiler.get_compiled_template(template_id, data)
            rendered = compiled.render(context)
            # Return rendered string as-is (filters control the output format)
            return rendered
        else:
            # Return primitive types as-is (int, float, bool, None)
            return data
