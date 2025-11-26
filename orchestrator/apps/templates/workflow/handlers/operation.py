"""
OperationHandler for Workflow Engine.

Executes operation nodes by rendering templates and creating batch operations.
"""

import logging
import time
from typing import Any, Dict

from apps.templates.engine.exceptions import TemplateRenderError, TemplateValidationError
from apps.templates.engine.renderer import TemplateRenderer
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowExecution, WorkflowNode

from .base import BaseNodeHandler, NodeExecutionMode, NodeExecutionResult

logger = logging.getLogger(__name__)


class OperationHandler(BaseNodeHandler):
    """
    Handler for Operation nodes.

    Flow:
        1. Get OperationTemplate by node.template_id
        2. Render template via TemplateRenderer (Track 1 integration)
        3. [Week 9] Create BatchOperation from rendered data
        4. Execute operation (sync: wait, async: return task_id)
        5. Return NodeExecutionResult

    Current Implementation (Week 7-8):
        - Returns rendered data as output (no BatchOperation yet)
        - SYNC mode only (ASYNC requires Celery - Week 9)

    Integration:
        - apps.templates.models.OperationTemplate: Template storage
        - apps.templates.engine.renderer.TemplateRenderer: Rendering
    """

    def __init__(self):
        """Initialize OperationHandler with TemplateRenderer."""
        self.renderer = TemplateRenderer()

    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute operation node by rendering template.

        Args:
            node: WorkflowNode with template_id
            context: Execution context with variables
            execution: WorkflowExecution for tracking
            mode: Execution mode (currently only SYNC supported)

        Returns:
            NodeExecutionResult with rendered data or error
        """
        start_time = time.time()

        # Create step result for audit
        step_result = self._create_step_result(
            execution=execution,
            node=node,
            input_data={'context_keys': list(context.keys())}
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
                    'mode': mode.value
                }
            )

            # 2. Render template with validation
            rendered_data = self.renderer.render(
                template=template,
                context_data=context,
                validate=True
            )

            # 3. TODO Week 9: Create BatchOperation from rendered_data
            # For now, return rendered data as output

            # 4. Execute operation (Week 9: Celery integration)
            # Current: SYNC mode only - return rendered data immediately
            if mode == NodeExecutionMode.ASYNC:
                logger.warning(
                    f"ASYNC mode requested but not implemented (Week 9) - using SYNC",
                    extra={'node_id': node.id}
                )

            duration = time.time() - start_time

            # 5. Return success result
            result = NodeExecutionResult(
                success=True,
                output=rendered_data,
                error=None,
                mode=NodeExecutionMode.SYNC,  # Force SYNC for now
                duration_seconds=duration
            )

            # Update step result
            self._update_step_result(step_result, result)

            logger.info(
                f"Operation node {node.id} completed successfully",
                extra={
                    'node_id': node.id,
                    'duration_seconds': duration,
                    'output_size': len(str(rendered_data))
                }
            )

            return result

        except OperationTemplate.DoesNotExist:
            error_msg = f"OperationTemplate not found: {node.template_id}"
            logger.error(error_msg, extra={'node_id': node.id, 'template_id': node.template_id})

            result = NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=time.time() - start_time
            )
            self._update_step_result(step_result, result)
            return result

        except (TemplateRenderError, TemplateValidationError) as exc:
            error_msg = f"Template rendering failed: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id, 'template_id': node.template_id},
                exc_info=True
            )

            result = NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=time.time() - start_time
            )
            self._update_step_result(step_result, result)
            return result

        except Exception as exc:
            error_msg = f"Unexpected error executing operation node: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id},
                exc_info=True
            )

            result = NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=time.time() - start_time
            )
            self._update_step_result(step_result, result)
            return result
