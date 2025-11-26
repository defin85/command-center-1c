"""
REST API Views for Workflow Engine.

Provides ViewSets for:
- WorkflowTemplateViewSet: CRUD + validate, execute, clone
- WorkflowExecutionViewSet: Read-only + cancel, steps, status
"""

import logging
import threading
from typing import Any, Dict

from django.db import models, transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .engine import WorkflowEngine, WorkflowEngineError, get_workflow_engine
from .filters import WorkflowExecutionFilter, WorkflowTemplateFilter
from .models import WorkflowExecution, WorkflowStepResult, WorkflowTemplate
from .serializers import (
    WorkflowCancelResponseSerializer,
    WorkflowCloneRequestSerializer,
    WorkflowCloneResponseSerializer,
    WorkflowExecuteRequestSerializer,
    WorkflowExecuteResponseSerializer,
    WorkflowExecutionDetailSerializer,
    WorkflowExecutionListSerializer,
    WorkflowStatusResponseSerializer,
    WorkflowStepResultSerializer,
    WorkflowTemplateDetailSerializer,
    WorkflowTemplateListSerializer,
    WorkflowValidateResponseSerializer,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Throttle Classes
# ============================================================================


class WorkflowExecuteThrottle(UserRateThrottle):
    """Rate limit for workflow execute endpoint: 30/min."""

    rate = '30/min'
    scope = 'workflow_execute'


# ============================================================================
# WorkflowTemplateViewSet
# ============================================================================


@extend_schema_view(
    list=extend_schema(
        summary="List workflow templates",
        description="Returns paginated list of workflow templates without DAG structure.",
        tags=['Workflows'],
    ),
    retrieve=extend_schema(
        summary="Get workflow template details",
        description="Returns full workflow template including DAG structure and config.",
        tags=['Workflows'],
    ),
    create=extend_schema(
        summary="Create workflow template",
        description="Creates a new workflow template with DAG structure.",
        tags=['Workflows'],
    ),
    update=extend_schema(
        summary="Update workflow template",
        description="Updates workflow template. Resets is_valid if DAG changes.",
        tags=['Workflows'],
    ),
    partial_update=extend_schema(
        summary="Partial update workflow template",
        description="Partially updates workflow template fields.",
        tags=['Workflows'],
    ),
    destroy=extend_schema(
        summary="Delete workflow template",
        description="Deletes workflow template. Protected if has executions.",
        tags=['Workflows'],
    ),
)
class WorkflowTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Workflow Template CRUD operations.

    Endpoints:
    - GET /api/v1/workflows/ - List templates
    - POST /api/v1/workflows/ - Create template
    - GET /api/v1/workflows/{id}/ - Get template details
    - PUT /api/v1/workflows/{id}/ - Update template
    - PATCH /api/v1/workflows/{id}/ - Partial update
    - DELETE /api/v1/workflows/{id}/ - Delete template
    - POST /api/v1/workflows/{id}/validate/ - Validate DAG
    - POST /api/v1/workflows/{id}/execute/ - Execute workflow
    - POST /api/v1/workflows/{id}/clone/ - Clone as new version
    """

    # Note: execution_count is annotated to avoid N+1 queries in list view
    # The annotation is used by WorkflowTemplateListSerializer.get_execution_count()
    queryset = WorkflowTemplate.objects.select_related(
        'created_by', 'parent_version'
    ).annotate(
        _execution_count=models.Count('executions')
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WorkflowTemplateFilter
    search_fields = ['name', 'description', 'workflow_type']
    ordering_fields = ['name', 'created_at', 'updated_at', 'version_number']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if self.action == 'list':
            return WorkflowTemplateListSerializer
        return WorkflowTemplateDetailSerializer

    def perform_create(self, serializer):
        """Set created_by on create."""
        instance = serializer.save(created_by=self.request.user)
        logger.info(
            f"WorkflowTemplate created: id={instance.id}, name={instance.name}, "
            f"user={self.request.user.username}"
        )

    def destroy(self, request, *args, **kwargs):
        """
        Delete workflow template.

        Protected if template has executions - use is_active=False instead.
        """
        instance = self.get_object()

        # Check for existing executions
        execution_count = instance.executions.count()
        if execution_count > 0:
            logger.warning(
                f"Delete blocked for WorkflowTemplate id={instance.id}: "
                f"has {execution_count} executions, user={request.user.username}"
            )
            return Response(
                {
                    'error': 'Cannot delete template with existing executions',
                    'execution_count': execution_count,
                    'hint': 'Set is_active=False to deactivate instead',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            f"WorkflowTemplate deleted: id={instance.id}, name={instance.name}, "
            f"user={request.user.username}"
        )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Validate workflow template",
        description="""
        Validates the workflow template DAG structure.

        Checks:
        - Pydantic schema validation
        - Node IDs are unique
        - Edge references valid nodes
        - No cycles (Kahn's algorithm)
        - Proper topology (start/end nodes exist)
        """,
        request=None,
        responses={
            200: WorkflowValidateResponseSerializer,
            400: WorkflowValidateResponseSerializer,
        },
        tags=['Workflows'],
    )
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Validate workflow template DAG structure.

        POST /api/v1/workflows/{id}/validate/
        """
        template = self.get_object()

        try:
            template.validate()
            template.save(update_fields=['is_valid'])

            # Get warnings if any
            warnings = []
            if hasattr(template, '_validation_metadata'):
                warnings = template._validation_metadata.get('warnings', [])

            return Response(
                WorkflowValidateResponseSerializer({
                    'valid': True,
                    'errors': [],
                    'warnings': warnings,
                    'metadata': getattr(template, '_validation_metadata', {}).get(
                        'validation_metadata', {}
                    ),
                }).data
            )

        except ValueError as exc:
            return Response(
                WorkflowValidateResponseSerializer({
                    'valid': False,
                    'errors': [str(exc)],
                    'warnings': [],
                    'metadata': {},
                }).data,
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Execute workflow template",
        description="""
        Executes the workflow template.

        Modes:
        - sync: Blocking execution, returns result when complete
        - async: Background execution, returns execution_id immediately

        Rate limited to 30 requests per minute.
        """,
        request=WorkflowExecuteRequestSerializer,
        responses={
            200: WorkflowExecuteResponseSerializer,
            202: WorkflowExecuteResponseSerializer,
            400: OpenApiResponse(description="Validation error or template not valid"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
        tags=['Workflows'],
    )
    @action(
        detail=True,
        methods=['post'],
        throttle_classes=[WorkflowExecuteThrottle],
    )
    def execute(self, request, pk=None):
        """
        Execute workflow template.

        POST /api/v1/workflows/{id}/execute/

        Body:
        {
            "input_context": {"key": "value"},
            "mode": "async"  // or "sync"
        }
        """
        template = self.get_object()

        # Validate request
        serializer = WorkflowExecuteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        input_context = serializer.validated_data.get('input_context', {})
        mode = serializer.validated_data.get('mode', 'async')

        # Check template is valid and active
        if not template.is_valid:
            return Response(
                {
                    'error': 'Template is not validated',
                    'hint': 'Call /validate/ endpoint first',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not template.is_active:
            return Response(
                {'error': 'Template is not active'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        engine = get_workflow_engine()

        logger.info(
            f"Workflow execute requested: template_id={template.id}, "
            f"mode={mode}, user={request.user.username}"
        )

        if mode == 'sync':
            # Synchronous execution
            try:
                execution = engine.execute_workflow(template, input_context)

                logger.info(
                    f"Workflow sync execution completed: execution_id={execution.id}, "
                    f"status={execution.status}, duration={execution.duration}s"
                )

                return Response(
                    WorkflowExecuteResponseSerializer({
                        'execution_id': execution.id,
                        'status': execution.status,
                        'mode': 'sync',
                        'message': f'Workflow {execution.status}',
                        'final_result': execution.final_result,
                        'duration': execution.duration,
                        'error_message': execution.error_message or '',
                    }).data,
                    status=status.HTTP_200_OK,
                )

            except WorkflowEngineError as exc:
                logger.error(
                    f"Workflow sync execution failed: template_id={template.id}, "
                    f"execution_id={exc.execution_id}, error={exc.message}"
                )
                return Response(
                    {'error': exc.message, 'execution_id': exc.execution_id},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        else:
            # Asynchronous execution
            # Create execution in pending state
            execution = template.create_execution(input_context)

            # Start execution in background thread
            # TODO(Week 11): Replace threading.Thread with Celery task for:
            # - Proper task tracking and monitoring
            # - Graceful shutdown handling
            # - Distributed execution support
            # - Rate limiting and concurrency control
            def _run_workflow_async():
                """Execute workflow in background with error handling."""
                try:
                    engine.execute_workflow(template, input_context)
                except Exception as exc:
                    logger.error(
                        f"Async execution {execution.id} failed: {exc}",
                        exc_info=True,
                    )
                    # Try to mark as failed
                    try:
                        with transaction.atomic():
                            execution.refresh_from_db()
                            if execution.status == WorkflowExecution.STATUS_PENDING:
                                execution.start()
                            if execution.status == WorkflowExecution.STATUS_RUNNING:
                                execution.fail(str(exc))
                            execution.save()
                    except Exception:
                        logger.exception(
                            f"Failed to update execution {execution.id} status after error"
                        )

            thread = threading.Thread(
                target=_run_workflow_async,
                name=f'workflow-{execution.id}',
                daemon=True,
            )
            thread.start()

            logger.info(
                f"Workflow async execution started: execution_id={execution.id}, "
                f"template_id={template.id}, thread={thread.name}"
            )

            return Response(
                WorkflowExecuteResponseSerializer({
                    'execution_id': execution.id,
                    'status': 'pending',
                    'mode': 'async',
                    'message': 'Workflow execution started in background',
                }).data,
                status=status.HTTP_202_ACCEPTED,
            )

    @extend_schema(
        summary="Clone workflow template as new version",
        description="""
        Creates a new version of the workflow template.

        The new template:
        - Has incremented version_number
        - References original as parent_version
        - Copies DAG structure and config
        - Is set as active
        """,
        request=WorkflowCloneRequestSerializer,
        responses={
            201: WorkflowCloneResponseSerializer,
        },
        tags=['Workflows'],
    )
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """
        Clone workflow template as new version.

        POST /api/v1/workflows/{id}/clone/

        Body (optional):
        {
            "name": "New Name"  // Override name
        }
        """
        template = self.get_object()

        serializer = WorkflowCloneRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_name = serializer.validated_data.get('name')

        # Clone template
        new_template = template.clone_as_new_version(created_by=request.user)

        # Override name if provided
        if new_name:
            new_template.name = new_name
            new_template.save(update_fields=['name'])

        return Response(
            WorkflowCloneResponseSerializer({
                'id': new_template.id,
                'name': new_template.name,
                'version_number': new_template.version_number,
                'message': f'Cloned from v{template.version_number}',
            }).data,
            status=status.HTTP_201_CREATED,
        )


# ============================================================================
# WorkflowExecutionViewSet
# ============================================================================


@extend_schema_view(
    list=extend_schema(
        summary="List workflow executions",
        description="Returns paginated list of workflow executions.",
        tags=['Workflow Executions'],
    ),
    retrieve=extend_schema(
        summary="Get workflow execution details",
        description="Returns full execution details including step results.",
        tags=['Workflow Executions'],
    ),
)
class WorkflowExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Workflow Execution read operations.

    Endpoints:
    - GET /api/v1/executions/ - List executions
    - GET /api/v1/executions/{id}/ - Get execution details
    - POST /api/v1/executions/{id}/cancel/ - Cancel execution
    - GET /api/v1/executions/{id}/steps/ - Get step results
    - GET /api/v1/executions/{id}/status/ - Lightweight status polling
    """

    queryset = WorkflowExecution.objects.select_related(
        'workflow_template'
    ).prefetch_related('step_results')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WorkflowExecutionFilter
    search_fields = ['workflow_template__name', 'trace_id']
    ordering_fields = ['started_at', 'completed_at', 'status']
    ordering = ['-started_at']

    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if self.action == 'list':
            return WorkflowExecutionListSerializer
        return WorkflowExecutionDetailSerializer

    @extend_schema(
        summary="Cancel workflow execution",
        description="""
        Cancels a running or pending workflow execution.

        Only executions in 'pending' or 'running' state can be cancelled.
        """,
        request=None,
        responses={
            200: WorkflowCancelResponseSerializer,
            400: OpenApiResponse(description="Execution cannot be cancelled"),
        },
        tags=['Workflow Executions'],
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel workflow execution.

        POST /api/v1/executions/{id}/cancel/
        """
        execution = self.get_object()
        original_status = execution.status
        engine = get_workflow_engine()

        cancelled = engine.cancel_workflow(str(execution.id))

        # Refresh to get current state
        execution.refresh_from_db()

        if cancelled:
            logger.info(
                f"Workflow execution cancelled: execution_id={execution.id}, "
                f"previous_status={original_status}, user={request.user.username}"
            )
            return Response(
                WorkflowCancelResponseSerializer({
                    'execution_id': execution.id,
                    'cancelled': True,
                    'status': execution.status,
                    'message': 'Execution cancelled successfully',
                }).data
            )
        else:
            logger.warning(
                f"Workflow cancel failed: execution_id={execution.id}, "
                f"status={execution.status}, user={request.user.username}"
            )
            return Response(
                WorkflowCancelResponseSerializer({
                    'execution_id': execution.id,
                    'cancelled': False,
                    'status': execution.status,
                    'message': f'Cannot cancel execution in {execution.status} state',
                }).data,
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get execution step results",
        description="Returns all step results for the execution.",
        responses={
            200: WorkflowStepResultSerializer(many=True),
        },
        tags=['Workflow Executions'],
    )
    @action(detail=True, methods=['get'])
    def steps(self, request, pk=None):
        """
        Get execution step results.

        GET /api/v1/executions/{id}/steps/
        """
        execution = self.get_object()
        step_results = execution.step_results.all().order_by('started_at')

        serializer = WorkflowStepResultSerializer(step_results, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get execution status (lightweight)",
        description="""
        Returns lightweight status for polling.

        Optimized for frequent polling - returns minimal data.
        Use retrieve endpoint for full details.
        """,
        responses={
            200: WorkflowStatusResponseSerializer,
        },
        tags=['Workflow Executions'],
    )
    @method_decorator(never_cache)
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Get lightweight execution status for polling.

        GET /api/v1/executions/{id}/status/
        """
        execution = self.get_object()

        data = {
            'execution_id': execution.id,
            'status': execution.status,
            'progress_percent': execution.progress_percent,
            'current_node_id': execution.current_node_id or '',
            'completed_nodes': execution.completed_nodes,
            'failed_nodes': execution.failed_nodes,
            'started_at': execution.started_at,
            'completed_at': execution.completed_at,
            'duration': execution.duration,
        }

        # Add result/error for terminal states
        if execution.status == WorkflowExecution.STATUS_COMPLETED:
            data['final_result'] = execution.final_result
        elif execution.status == WorkflowExecution.STATUS_FAILED:
            data['error_message'] = execution.error_message or ''
            data['error_node_id'] = execution.error_node_id or ''

        serializer = WorkflowStatusResponseSerializer(data)
        return Response(serializer.data)
