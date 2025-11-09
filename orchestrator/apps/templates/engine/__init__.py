"""
Template Engine for CommandCenter1C.

Main exports:
- TemplateRenderer: Main facade for template rendering
- TemplateError, TemplateValidationError, TemplateRenderError: Exceptions

Note: Custom filters and tests are registered automatically
when TemplateRenderer is instantiated.
"""

from .renderer import TemplateRenderer
from .validator import TemplateValidator
from .compiler import TemplateCompiler
from .exceptions import (
    TemplateError,
    TemplateValidationError,
    TemplateRenderError,
    TemplateSyntaxError,
)
from .context import ContextBuilder
from .filters import register_custom_filters
from .tests import register_custom_tests

__all__ = [
    'TemplateRenderer',
    'TemplateValidator',
    'TemplateCompiler',
    'TemplateError',
    'TemplateValidationError',
    'TemplateRenderError',
    'TemplateSyntaxError',
    'ContextBuilder',
    'register_custom_filters',
    'register_custom_tests',
]
