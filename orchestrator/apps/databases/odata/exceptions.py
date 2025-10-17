# orchestrator/apps/databases/odata/exceptions.py
"""Custom exceptions для OData client."""


class ODataError(Exception):
    """Base exception для всех OData errors."""
    pass


class ODataConnectionError(ODataError):
    """Connection к OData endpoint failed."""
    pass


class ODataAuthenticationError(ODataError):
    """Authentication failed (401)."""
    pass


class ODataRequestError(ODataError):
    """HTTP request failed (4xx, 5xx)."""

    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class OData1CSpecificError(ODataError):
    """1С-specific error (например, нарушение уникальности кода)."""
    pass


class ODataTimeoutError(ODataError):
    """Request timeout."""
    pass
