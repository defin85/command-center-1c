"""
Context builder for template rendering.
"""

from typing import Dict, Any
from datetime import datetime
import uuid


class ContextBuilder:
    """Builds safe context for template rendering."""

    def build_context(
        self,
        template,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build context for template rendering.

        Args:
            template: OperationTemplate instance
            data: User-provided context data

        Returns:
            Safe context dict
        """
        context = {}

        # 1. Add user-provided data (sanitized)
        context.update(self._sanitize_data(data))

        # 2. Add system variables
        context['current_timestamp'] = datetime.now()
        context['current_date'] = datetime.now().date()
        context['template_id'] = str(template.id)
        context['template_name'] = template.name
        context['operation_type'] = template.operation_type

        # 3. Add helper functions
        context['uuid4'] = lambda: str(uuid.uuid4())

        return context

    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize user-provided data.

        Removes dangerous keys, validates types, converts datetime/date to ISO strings.
        """
        from datetime import datetime, date

        sanitized = {}

        # Blacklist dangerous keys
        dangerous_keys = {'__builtins__', '__globals__', '__class__'}

        for key, value in data.items():
            # Skip dangerous keys
            if key in dangerous_keys or key.startswith('_'):
                continue

            # Convert datetime/date objects to ISO format strings for Jinja2
            if isinstance(value, datetime):
                # Keep datetime objects as-is so filters can access them
                sanitized[key] = value
            elif isinstance(value, date):
                # Keep date objects as-is so filters can access them
                sanitized[key] = value
            elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
                # Primitives pass through
                sanitized[key] = value

        return sanitized
