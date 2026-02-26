"""
OData Client для работы с 1С:Предприятие 8.3 OData API.

Основные компоненты:
- ODataClient: HTTP client для работы с OData
- SessionManager: Управление пулом connections
- Exceptions: Custom исключения для error handling
"""

from .client import ODataClient
from .metadata_adapter import ODataMetadataAdapter, ODataMetadataTransportError
from .session_manager import ODataSessionManager, session_manager
from .exceptions import (
    ODataError,
    ODataConnectionError,
    ODataAuthenticationError,
    ODataRequestError,
    OData1CSpecificError,
    ODataTimeoutError
)

__all__ = [
    'ODataClient',
    'ODataMetadataAdapter',
    'ODataMetadataTransportError',
    'ODataSessionManager',
    'session_manager',
    'ODataError',
    'ODataConnectionError',
    'ODataAuthenticationError',
    'ODataRequestError',
    'OData1CSpecificError',
    'ODataTimeoutError',
]
