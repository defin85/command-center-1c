"""
RAS Backend for Workflow Engine.

Handles RAS-based cluster management operations:
- lock_scheduled_jobs: Block scheduled jobs (reglament tasks)
- unlock_scheduled_jobs: Enable scheduled jobs
- terminate_sessions: Terminate all sessions for infobase
- block_sessions: Block new user connections
- unblock_sessions: Allow new user connections
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from django.conf import settings
import httpx

from apps.databases.models import Database
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowExecution

# Import generated RAS adapter client
from apps.databases.clients.generated.ras_adapter_api_client import Client
from apps.databases.clients.generated.ras_adapter_api_client.api.infobases_v2 import (
    lock_infobase_v2,
    unlock_infobase_v2,
    block_sessions_v2,
    unblock_sessions_v2,
)
from apps.databases.clients.generated.ras_adapter_api_client.api.sessions_v2 import (
    terminate_sessions_v2,
)
from apps.databases.clients.generated.ras_adapter_api_client.models import (
    LockInfobaseRequestV2,
    UnlockInfobaseRequestV2,
    BlockSessionsRequestV2,
    UnblockSessionsRequestV2,
    TerminateSessionsRequestV2,
    ErrorResponse,
    SuccessResponse,
)

from ..base import NodeExecutionMode, NodeExecutionResult
from .base import AbstractOperationBackend

logger = logging.getLogger(__name__)


# RAS operation type constants
TYPE_LOCK_SCHEDULED_JOBS = 'lock_scheduled_jobs'
TYPE_UNLOCK_SCHEDULED_JOBS = 'unlock_scheduled_jobs'
TYPE_TERMINATE_SESSIONS = 'terminate_sessions'
TYPE_BLOCK_SESSIONS = 'block_sessions'
TYPE_UNBLOCK_SESSIONS = 'unblock_sessions'


class RASBackendError(Exception):
    """Exception raised when RAS operation fails."""

    def __init__(self, message: str, database_id: Optional[str] = None, details: Optional[str] = None):
        super().__init__(message)
        self.database_id = database_id
        self.details = details


class RASBackend(AbstractOperationBackend):
    """
    RAS Backend for cluster management operations.

    Executes operations directly via RAS Adapter HTTP API (sync).
    Does NOT use Celery - operations are fast (< 1 second) and direct.

    Supported operation types:
        - lock_scheduled_jobs: Disable scheduled jobs
        - unlock_scheduled_jobs: Enable scheduled jobs
        - terminate_sessions: Terminate all sessions
        - block_sessions: Block new connections
        - unblock_sessions: Allow new connections
    """

    # Operation types handled by RAS backend
    SUPPORTED_TYPES: Set[str] = {
        TYPE_LOCK_SCHEDULED_JOBS,
        TYPE_UNLOCK_SCHEDULED_JOBS,
        TYPE_TERMINATE_SESSIONS,
        TYPE_BLOCK_SESSIONS,
        TYPE_UNBLOCK_SESSIONS,
    }

    # Default timeout for RAS operations (seconds)
    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        """
        Initialize RAS Backend.

        Args:
            base_url: RAS Adapter URL (default: from settings.RAS_ADAPTER_URL)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = (
            base_url or
            getattr(settings, 'RAS_ADAPTER_URL', 'http://localhost:8188')
        ).rstrip('/')
        self.timeout = timeout or self.DEFAULT_TIMEOUT_SECONDS

    def _get_client(self) -> Client:
        """Create RAS Adapter client instance."""
        return Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(float(self.timeout))
        )

    def execute(
        self,
        template: OperationTemplate,
        rendered_data: Dict[str, Any],
        target_databases: List[str],
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute RAS operation on target databases.

        RAS operations are always synchronous (fast, < 1 second per database).
        Mode parameter is accepted for API compatibility but ASYNC is not supported.

        Args:
            template: OperationTemplate with operation_type
            rendered_data: Rendered template data (may contain db_user, db_password)
            target_databases: List of database UUIDs
            context: Execution context
            execution: WorkflowExecution for tracking
            mode: Execution mode (only SYNC is actually supported)

        Returns:
            NodeExecutionResult with operation outcome
        """
        start_time = time.time()
        operation_type = template.operation_type

        logger.info(
            f"RASBackend executing {operation_type}",
            extra={
                'template_id': template.id,
                'template_name': template.name,
                'operation_type': operation_type,
                'target_count': len(target_databases),
                'mode': mode.value
            }
        )

        # Warn if ASYNC mode requested
        if mode == NodeExecutionMode.ASYNC:
            logger.warning(
                "RASBackend does not support ASYNC mode, executing synchronously",
                extra={'operation_type': operation_type}
            )

        results = []
        errors = []

        # Create client once and reuse for all databases
        client = self._get_client()
        try:
            # Execute for each target database
            for db_id in target_databases:
                try:
                    result = self._execute_single(
                        client=client,
                        database_id=db_id,
                        operation_type=operation_type,
                        rendered_data=rendered_data
                    )
                    results.append({
                        'database_id': db_id,
                        'success': True,
                        'result': result
                    })
                except RASBackendError as exc:
                    logger.error(
                        f"RAS operation failed for database {db_id}: {exc}",
                        extra={
                            'database_id': db_id,
                            'operation_type': operation_type,
                            'details': exc.details
                        }
                    )
                    errors.append({
                        'database_id': db_id,
                        'success': False,
                        'error': str(exc),
                        'details': exc.details
                    })
                except Exception as exc:
                    logger.error(
                        f"Unexpected error for database {db_id}: {exc}",
                        extra={'database_id': db_id},
                        exc_info=True
                    )
                    errors.append({
                        'database_id': db_id,
                        'success': False,
                        'error': str(exc)
                    })
        finally:
            # Close client connection once after all databases are processed
            if hasattr(client, '_client') and client._client is not None:
                client._client.close()

        duration = time.time() - start_time
        success = len(errors) == 0
        total = len(target_databases)
        completed = len(results)
        failed = len(errors)

        output = {
            'backend': 'ras',
            'operation_type': operation_type,
            'total': total,
            'completed': completed,
            'failed': failed,
            'results': results,
            'errors': errors if errors else None
        }

        logger.info(
            f"RASBackend completed {operation_type}",
            extra={
                'success': success,
                'total': total,
                'completed': completed,
                'failed': failed,
                'duration_seconds': duration
            }
        )

        return NodeExecutionResult(
            success=success,
            output=output,
            error=f"{failed} of {total} operations failed" if errors else None,
            mode=NodeExecutionMode.SYNC,  # Always sync
            duration_seconds=duration,
            operation_id=None,  # RAS operations don't create BatchOperation
            task_id=None
        )

    def _execute_single(
        self,
        client: Client,
        database_id: str,
        operation_type: str,
        rendered_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute RAS operation for a single database.

        Args:
            client: RAS Adapter client instance (reused from execute())
            database_id: Database UUID string
            operation_type: RAS operation type
            rendered_data: Template parameters (db_user, db_password, etc.)

        Returns:
            Dict with operation result

        Raises:
            RASBackendError: If operation fails
        """
        # 1. Get Database and extract RAS identifiers
        try:
            database = Database.objects.select_related('cluster').get(id=database_id)
        except Database.DoesNotExist:
            raise RASBackendError(
                f"Database not found: {database_id}",
                database_id=database_id
            )

        # Get cluster and infobase UUIDs
        cluster_id = self._get_cluster_uuid(database)
        infobase_id = self._get_infobase_uuid(database)

        if not cluster_id:
            raise RASBackendError(
                f"Database {database.name} has no cluster UUID configured",
                database_id=database_id,
                details="Set ras_cluster_id on Database or ras_cluster_uuid on Cluster"
            )

        if not infobase_id:
            raise RASBackendError(
                f"Database {database.name} has no infobase UUID configured",
                database_id=database_id,
                details="Set ras_infobase_id on Database model"
            )

        # 2. Extract credentials from rendered_data or database
        db_user = rendered_data.get('db_user') or database.username or ''
        db_password = rendered_data.get('db_password') or database.password or ''

        # 3. Execute operation
        try:
            if operation_type == TYPE_LOCK_SCHEDULED_JOBS:
                return self._lock_scheduled_jobs(client, cluster_id, infobase_id, db_user, db_password)
            elif operation_type == TYPE_UNLOCK_SCHEDULED_JOBS:
                return self._unlock_scheduled_jobs(client, cluster_id, infobase_id, db_user, db_password)
            elif operation_type == TYPE_TERMINATE_SESSIONS:
                return self._terminate_sessions(client, cluster_id, infobase_id)
            elif operation_type == TYPE_BLOCK_SESSIONS:
                return self._block_sessions(client, cluster_id, infobase_id, db_user, db_password, rendered_data)
            elif operation_type == TYPE_UNBLOCK_SESSIONS:
                return self._unblock_sessions(client, cluster_id, infobase_id, db_user, db_password)
            else:
                raise RASBackendError(
                    f"Unsupported RAS operation type: {operation_type}",
                    database_id=database_id
                )
        except httpx.TimeoutException as exc:
            raise RASBackendError(
                f"RAS operation timed out after {self.timeout}s",
                database_id=database_id,
                details=str(exc)
            )
        except httpx.HTTPError as exc:
            raise RASBackendError(
                f"HTTP error during RAS operation: {exc}",
                database_id=database_id,
                details=str(exc)
            )

    def _get_cluster_uuid(self, database: Database) -> Optional[UUID]:
        """Get cluster UUID from database or its cluster."""
        # Prefer database.ras_cluster_id if set
        if database.ras_cluster_id:
            return database.ras_cluster_id

        # Fallback to cluster.ras_cluster_uuid
        if database.cluster and database.cluster.ras_cluster_uuid:
            return database.cluster.ras_cluster_uuid

        return None

    def _get_infobase_uuid(self, database: Database) -> Optional[UUID]:
        """Get infobase UUID from database."""
        return database.ras_infobase_id

    def _lock_scheduled_jobs(
        self,
        client: Client,
        cluster_id: UUID,
        infobase_id: UUID,
        db_user: str,
        db_password: str
    ) -> Dict[str, Any]:
        """Lock scheduled jobs (disable reglament tasks)."""
        request = LockInfobaseRequestV2(
            db_user=db_user if db_user else None,
            db_password=db_password if db_password else None
        )

        response = lock_infobase_v2.sync(
            client=client,
            body=request,
            cluster_id=cluster_id,
            infobase_id=infobase_id
        )

        return self._handle_response(response, 'lock_scheduled_jobs')

    def _unlock_scheduled_jobs(
        self,
        client: Client,
        cluster_id: UUID,
        infobase_id: UUID,
        db_user: str,
        db_password: str
    ) -> Dict[str, Any]:
        """Unlock scheduled jobs (enable reglament tasks)."""
        request = UnlockInfobaseRequestV2(
            db_user=db_user if db_user else None,
            db_password=db_password if db_password else None
        )

        response = unlock_infobase_v2.sync(
            client=client,
            body=request,
            cluster_id=cluster_id,
            infobase_id=infobase_id
        )

        return self._handle_response(response, 'unlock_scheduled_jobs')

    def _terminate_sessions(
        self,
        client: Client,
        cluster_id: UUID,
        infobase_id: UUID
    ) -> Dict[str, Any]:
        """Terminate all sessions for infobase."""
        request = TerminateSessionsRequestV2()

        response = terminate_sessions_v2.sync(
            client=client,
            body=request,
            cluster_id=cluster_id,
            infobase_id=infobase_id
        )

        return self._handle_response(response, 'terminate_sessions')

    def _block_sessions(
        self,
        client: Client,
        cluster_id: UUID,
        infobase_id: UUID,
        db_user: str,
        db_password: str,
        rendered_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Block new user connections."""
        request = BlockSessionsRequestV2(
            db_user=db_user if db_user else None,
            db_password=db_password if db_password else None,
            denied_message=rendered_data.get('denied_message'),
            permission_code=rendered_data.get('permission_code')
        )

        response = block_sessions_v2.sync(
            client=client,
            body=request,
            cluster_id=cluster_id,
            infobase_id=infobase_id
        )

        return self._handle_response(response, 'block_sessions')

    def _unblock_sessions(
        self,
        client: Client,
        cluster_id: UUID,
        infobase_id: UUID,
        db_user: str,
        db_password: str
    ) -> Dict[str, Any]:
        """Unblock user connections."""
        request = UnblockSessionsRequestV2(
            db_user=db_user if db_user else None,
            db_password=db_password if db_password else None
        )

        response = unblock_sessions_v2.sync(
            client=client,
            body=request,
            cluster_id=cluster_id,
            infobase_id=infobase_id
        )

        return self._handle_response(response, 'unblock_sessions')

    def _handle_response(self, response: Any, operation_name: str) -> Dict[str, Any]:
        """
        Handle RAS Adapter response.

        Args:
            response: Response from RAS Adapter (SuccessResponse, ErrorResponse, or None)
            operation_name: Name of operation for logging

        Returns:
            Dict with response details

        Raises:
            RASBackendError: If response indicates error
        """
        if response is None:
            raise RASBackendError(f"RAS Adapter returned empty response for {operation_name}")

        if isinstance(response, ErrorResponse):
            error_msg = response.error if hasattr(response, 'error') else 'Unknown error'
            details = getattr(response, 'details', None)
            raise RASBackendError(
                f"RAS operation {operation_name} failed: {error_msg}",
                details=details
            )

        if isinstance(response, SuccessResponse):
            return {
                'success': response.success,
                'message': response.message
            }

        # Handle other response types (BlockSessionsResponse, TerminateSessionsResponse)
        result = {}
        if hasattr(response, 'success'):
            result['success'] = response.success
        if hasattr(response, 'message'):
            result['message'] = response.message
        if hasattr(response, 'terminated_count'):
            result['terminated_count'] = response.terminated_count

        return result if result else {'success': True, 'message': 'Operation completed'}

    def supports_operation_type(self, operation_type: str) -> bool:
        """Check if this backend supports the given operation type."""
        return operation_type in self.SUPPORTED_TYPES

    @classmethod
    def get_supported_types(cls) -> Set[str]:
        """Get set of all operation types supported by this backend."""
        return cls.SUPPORTED_TYPES.copy()
