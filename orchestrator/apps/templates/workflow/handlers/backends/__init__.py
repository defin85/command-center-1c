"""
Operation backends for Workflow Engine.

Strategy pattern implementation for routing operations to different backends:
- ODataBackend: For OData-based operations (create, update, delete, query, install_extension)
- RASBackend: For RAS-based operations (lock/unlock scheduled jobs, block/unblock sessions, terminate)
"""

from .base import AbstractOperationBackend
from .odata import ODataBackend
from .ras import RASBackend

__all__ = [
    'AbstractOperationBackend',
    'ODataBackend',
    'RASBackend',
]
