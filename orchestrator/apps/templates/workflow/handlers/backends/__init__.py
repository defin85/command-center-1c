"""
Operation backends for Workflow Engine.

Strategy pattern implementation for routing operations to different backends:
- ODataBackend: For OData-based operations (create, update, delete, query, install_extension)
- RASBackend: For RAS-based operations (lock/unlock scheduled jobs, block/unblock sessions, terminate)
- IBCMDBackend: For ibcmd operations (ibcmd_backup, ibcmd_restore, ibcmd_replicate, ibcmd_create)
"""

from .base import AbstractOperationBackend
from .ibcmd import IBCMDBackend
from .odata import ODataBackend
from .ras import RASBackend

__all__ = [
    'AbstractOperationBackend',
    'IBCMDBackend',
    'ODataBackend',
    'RASBackend',
]
