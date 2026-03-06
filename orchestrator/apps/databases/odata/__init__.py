"""
OData Client для работы с 1С:Предприятие 8.3 OData API.

Основные компоненты:
- ODataClient: HTTP client для работы с OData
- SessionManager: Управление пулом connections
- Exceptions: Custom исключения для error handling
"""

from .client import ODataClient
from .document_adapter import ODataDocumentAdapter, ODataDocumentTransportError
from .metadata_adapter import ODataMetadataAdapter, ODataMetadataTransportError
from .session_manager import ODataSessionManager, session_manager
from .transport_options import resolve_database_odata_verify_tls
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
    'ODataDocumentAdapter',
    'ODataDocumentTransportError',
    'ODataMetadataAdapter',
    'ODataMetadataTransportError',
    'ODataSessionManager',
    'resolve_database_odata_verify_tls',
    'session_manager',
    'ODataError',
    'ODataConnectionError',
    'ODataAuthenticationError',
    'ODataRequestError',
    'OData1CSpecificError',
    'ODataTimeoutError',
]
