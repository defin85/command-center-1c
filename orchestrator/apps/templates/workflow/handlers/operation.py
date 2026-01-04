"""
OperationHandler for Workflow Engine.

Executes operation nodes by rendering templates and routing to appropriate backends.
Uses Strategy pattern to delegate execution to backend implementations.

Phase 4 Week 17: Full integration with Worker via BatchOperationFactory.
Enhanced: Strategy pattern for backend routing (OData/RAS/CLI/IBCMD).
"""

import logging
import time
from typing import Any, Dict, List, Optional

from apps.databases.models import Database
from apps.operations.waiter import OperationTimeoutError
from apps.templates.engine.exceptions import TemplateRenderError, TemplateValidationError
from apps.templates.engine.renderer import TemplateRenderer
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowExecution, WorkflowNode

from .base import BaseNodeHandler, NodeExecutionMode, NodeExecutionResult
from .backends import AbstractOperationBackend, CLIBackend, IBCMDBackend, ODataBackend, RASBackend

logger = logging.getLogger(__name__)


class OperationHandler(BaseNodeHandler):
    """
    Handler for Operation nodes with Strategy pattern for backend routing.

    Flow:
        1. Get OperationTemplate by node.template_id
        2. Render template via TemplateRenderer
        3. Extract target_databases from context
        4. Route to appropriate backend based on operation_type:
           - ODataBackend: create, update, delete, query
           - RASBackend: lock_scheduled_jobs, unlock_scheduled_jobs,
                        terminate_sessions, block_sessions, unblock_sessions
           - CLIBackend: designer_cli
        5. Execute via backend and return result

    Backend Selection (Strategy Pattern):
        - Each backend declares supported operation types
        - Handler iterates backends and selects first match
        - Default fallback to ODataBackend for backward compatibility
    """

    # Default timeout for SYNC mode (seconds)
    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(self):
        """Initialize OperationHandler with TemplateRenderer and backends."""
        self.renderer = TemplateRenderer()

        # Initialize backends in priority order
        # RASBackend checked first (more specific), ODataBackend as fallback
        self._backends: List[AbstractOperationBackend] = [
            RASBackend(),
            IBCMDBackend(),
            CLIBackend(),
            ODataBackend(),
        ]

    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute operation node by rendering template and routing to backend.

        Args:
            node: WorkflowNode with template_id
            context: Execution context with variables.
                     Expected keys:
                     - target_databases: List[str] - UUIDs of target databases
                     - user_id: str - User who initiated the workflow
            execution: WorkflowExecution for tracking
            mode: Execution mode (SYNC waits for completion, ASYNC returns immediately)

        Returns:
            NodeExecutionResult with operation result or queued status
        """
        start_time = time.time()

        # Create step result for audit
        step_result = self._create_step_result(
            execution=execution,
            node=node,
            input_data={
                'context_keys': list(context.keys()),
                'mode': mode.value
            }
        )

        try:
            # 1. Get OperationTemplate
            if not node.template_id:
                raise ValueError(f"Operation node {node.id} missing template_id")

            template = OperationTemplate.objects.get(id=node.template_id)

            logger.info(
                f"Executing operation node {node.id}",
                extra={
                    'node_id': node.id,
                    'template_id': node.template_id,
                    'template_name': template.name,
                    'operation_type': template.operation_type,
                    'mode': mode.value
                }
            )

            # 2. Render template with validation
            rendered_data = self.renderer.render(
                template=template,
                context_data=context,
                validate=True
            )

            # 3. Extract target_databases from context
            target_databases = self._extract_target_databases(context, node)

            if not target_databases:
                if context.get('dry_run'):
                    logger.info(
                        "Dry run enabled: skipping operation execution (no target databases specified)",
                        extra={'node_id': node.id}
                    )
                    return self._return_rendered_only(
                        rendered_data=rendered_data,
                        step_result=step_result,
                        start_time=start_time
                    )

                logger.warning(
                    "Missing target databases for operation node; failing execution",
                    extra={'node_id': node.id}
                )
                return self._return_error(
                    error_msg=(
                        "No target databases specified for operation execution. "
                        "Provide 'database_ids' (list) or 'target_databases' in workflow input_context, "
                        "or set 'dry_run': true to render only."
                    ),
                    step_result=step_result,
                    start_time=start_time,
                )

            # 4. Select backend based on operation_type
            backend = self._get_backend(template.operation_type)

            logger.info(
                f"Routing to {backend.__class__.__name__}",
                extra={
                    'node_id': node.id,
                    'operation_type': template.operation_type,
                    'backend': backend.__class__.__name__
                }
            )

            # 5. Prepare context with additional info
            execution_context = {
                **context,
                'node_id': str(node.id) if node else None,
                'timeout_seconds': self._get_timeout(node)
            }

            # 6. Execute via backend
            result = backend.execute(
                template=template,
                rendered_data=rendered_data,
                target_databases=target_databases,
                context=execution_context,
                execution=execution,
                mode=mode
            )

            # Update step result with backend result
            self._update_step_result(step_result, result)
            return result

        except OperationTemplate.DoesNotExist:
            error_msg = f"OperationTemplate not found: {node.template_id}"
            logger.error(error_msg, extra={'node_id': node.id, 'template_id': node.template_id})
            return self._return_error(error_msg, step_result, start_time)

        except (TemplateRenderError, TemplateValidationError) as exc:
            error_msg = f"Template rendering failed: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id, 'template_id': node.template_id},
                exc_info=True
            )
            return self._return_error(error_msg, step_result, start_time)

        except OperationTimeoutError as exc:
            error_msg = f"Operation timed out: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id, 'operation_id': exc.operation_id},
                exc_info=True
            )
            return self._return_error(
                error_msg,
                step_result,
                start_time,
                operation_id=exc.operation_id
            )

        except Database.DoesNotExist as exc:
            error_msg = f"Database not found: {str(exc)}"
            logger.error(error_msg, extra={'node_id': node.id}, exc_info=True)
            return self._return_error(error_msg, step_result, start_time)

        except ValueError as exc:
            error_msg = str(exc)
            logger.error(error_msg, extra={'node_id': node.id}, exc_info=True)
            return self._return_error(error_msg, step_result, start_time)

        except Exception as exc:
            error_msg = f"Unexpected error executing operation node: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id},
                exc_info=True
            )
            return self._return_error(error_msg, step_result, start_time)

    def _get_backend(self, operation_type: str) -> AbstractOperationBackend:
        """
        Select appropriate backend for operation type.

        Uses Strategy pattern - iterates backends and returns first match.
        ODataBackend is last in list and acts as default fallback.

        Args:
            operation_type: Operation type string (e.g., 'create', 'lock_scheduled_jobs')

        Returns:
            Backend instance that supports the operation type

        Raises:
            ValueError: If no backend supports the operation type
        """
        for backend in self._backends:
            if backend.supports_operation_type(operation_type):
                return backend

        # This should not happen if ODataBackend is configured as fallback
        # But handle gracefully just in case
        raise ValueError(
            f"No backend supports operation type: {operation_type}. "
            f"Available types: OData={ODataBackend.get_supported_types()}, "
            f"RAS={RASBackend.get_supported_types()}, "
            f"IBCMD={IBCMDBackend.get_supported_types()}"
        )

    def _get_timeout(self, node: WorkflowNode) -> int:
        """Get timeout from node config or use default."""
        if node.config:
            # NodeConfig is a Pydantic model - use model_dump() for safe access
            config_dict = node.config.model_dump() if hasattr(node.config, 'model_dump') else {}
            return config_dict.get('timeout_seconds', self.DEFAULT_TIMEOUT_SECONDS)
        return self.DEFAULT_TIMEOUT_SECONDS

    def _extract_target_databases(
        self,
        context: Dict[str, Any],
        node: WorkflowNode
    ) -> list:
        """
        Extract target database IDs from context.

        Checks multiple sources:
        1. context['target_databases'] - explicit list
        2. node.config.get('target_databases') - node-level config
        3. context['database_ids'] - list of database IDs (UI compatibility)
        4. context['database_id'] - single database (wrapped in list)

        Args:
            context: Execution context
            node: WorkflowNode with config

        Returns:
            List of database UUIDs (strings)
        """
        # 1. Explicit list in context
        target_dbs = context.get('target_databases')
        if target_dbs:
            # Ensure all are strings
            return [str(db) for db in target_dbs]

        # 2. Node-level config (NodeConfig is a Pydantic model, use getattr)
        if node.config:
            # NodeConfig is a Pydantic model - use model_dump() or getattr
            config_dict = node.config.model_dump() if hasattr(node.config, 'model_dump') else {}
            node_target_dbs = config_dict.get('target_databases')
            if node_target_dbs:
                return [str(db) for db in node_target_dbs]

        # 3. UI compatibility: database_ids list
        db_ids = context.get('database_ids')
        if db_ids:
            return [str(db) for db in db_ids]

        # 4. Single database fallback
        single_db = context.get('database_id')
        if single_db:
            return [str(single_db)]

        return []

    def _return_rendered_only(
        self,
        rendered_data: Dict[str, Any],
        step_result,
        start_time: float
    ) -> NodeExecutionResult:
        """Return result with rendered data only (no execution)."""
        duration = time.time() - start_time

        result = NodeExecutionResult(
            success=True,
            output={
                'rendered_data': rendered_data,
                'execution_skipped': True,
                'reason': 'Dry run: no target databases specified'
            },
            error=None,
            mode=NodeExecutionMode.SYNC,
            duration_seconds=duration,
            operation_id=None,
            task_id=None
        )

        self._update_step_result(step_result, result)
        return result

    def _return_error(
        self,
        error_msg: str,
        step_result,
        start_time: float,
        operation_id: Optional[str] = None
    ) -> NodeExecutionResult:
        """Return error result."""
        result = NodeExecutionResult(
            success=False,
            output=None,
            error=error_msg,
            mode=NodeExecutionMode.SYNC,
            duration_seconds=time.time() - start_time,
            operation_id=operation_id,
            task_id=None
        )

        self._update_step_result(step_result, result)
        return result

    @classmethod
    def get_all_supported_types(cls) -> Dict[str, List[str]]:
        """
        Get all supported operation types grouped by backend.

        Returns:
            Dict mapping backend name to list of supported types
        """
        return {
            'odata': list(ODataBackend.get_supported_types()),
            'ras': list(RASBackend.get_supported_types()),
            'ibcmd': list(IBCMDBackend.get_supported_types()),
            'cli': list(CLIBackend.get_supported_types()),
        }
