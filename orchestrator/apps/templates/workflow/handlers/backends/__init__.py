"""
Operation backends for Workflow Engine.

Strategy pattern implementation for routing operations to different backends:
- ODataBackend: For OData-based operations (create, update, delete, query)
- RASBackend: For RAS-based operations (lock/unlock scheduled jobs, block/unblock sessions, terminate)
- IBCMDBackend: For ibcmd operations (ibcmd_backup, ibcmd_restore, ibcmd_replicate, ibcmd_create)
- CLIBackend: For designer CLI operations (designer_cli)
"""

from .base import AbstractOperationBackend
from .cli import CLIBackend
from .ibcmd import IBCMDBackend
from .odata import ODataBackend
from .ras import RASBackend

__all__ = [
    'AbstractOperationBackend',
    'CLIBackend',
    'IBCMDBackend',
    'ODataBackend',
    'RASBackend',
]
