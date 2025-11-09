"""Custom exceptions for template engine."""


class TemplateError(Exception):
    """Base exception for template errors."""
    pass


class TemplateValidationError(TemplateError):
    """Raised when template validation fails."""
    pass


class TemplateRenderError(TemplateError):
    """Raised when template rendering fails."""
    pass


class TemplateSyntaxError(TemplateError):
    """Raised when template syntax is invalid."""
    pass
