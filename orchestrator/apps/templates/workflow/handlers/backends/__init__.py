"""
Operation backends for Workflow Engine.

Strategy pattern implementation for routing operations to different backends:
- PoolDomainBackend: For system-managed pool runtime operations (`pool.*`)
- ODataBackend: For OData-based operations (create, update, delete, query)
- RASBackend: For RAS-based operations (lock/unlock scheduled jobs, block/unblock sessions, terminate)
- IBCMDBackend: For schema-driven ibcmd operations (ibcmd_cli)
- CLIBackend: For designer CLI operations (designer_cli)
"""

from .base import AbstractOperationBackend
from .cli import CLIBackend
from .ibcmd import IBCMDBackend
from .odata import ODataBackend
from .pool_domain import PoolDomainBackend
from .ras import RASBackend

__all__ = [
    'AbstractOperationBackend',
    'CLIBackend',
    'IBCMDBackend',
    'ODataBackend',
    'PoolDomainBackend',
    'RASBackend',
]
