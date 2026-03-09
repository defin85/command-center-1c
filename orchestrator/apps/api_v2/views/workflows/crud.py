"""Workflow template CRUD endpoints."""

from __future__ import annotations

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core import permission_codes as perms
from apps.runtime_settings.effective import get_effective_runtime_setting
from apps.templates.workflow.models import (
    DAGStructure,
    WorkflowExecution,
    WorkflowTemplate,
)
from apps.templates.workflow.management_mode import (
    WORKFLOW_SYSTEM_MANAGED_READ_ONLY_CODE,
    WORKFLOW_SYSTEM_MANAGED_READ_ONLY_REASON,
    is_system_managed_workflow,
)
from apps.templates.workflow.authoring_boundary import (
    WORKFLOW_AUTHORING_BOUNDARY_VIOLATION_CODE,
    collect_authoring_boundary_violations,
)
from apps.templates.workflow.serializers import (
    WorkflowTemplateDetailSerializer,
)
from apps.api_v2.serializers.common import ErrorResponseSerializer
from .common import (
    _permission_denied,
    CloneWorkflowRequestSerializer,
    CreateWorkflowRequestSerializer,
    DeleteWorkflowRequestSerializer,
    UpdateWorkflowRequestSerializer,
    ValidateWorkflowRequestSerializer,
    WorkflowCloneResponseSerializer,
    WorkflowCreateResponseSerializer,
    WorkflowDeleteResponseSerializer,
    WorkflowUpdateResponseSerializer,
    WorkflowValidateResponseSerializer,
)

logger = logging.getLogger(__name__)

WORKFLOW_BINDING_ENFORCE_PINNED_KEY = "workflows.operation_binding.enforce_pinned"


def _resolve_request_tenant_id(request) -> str | None:
    tenant_id = str(getattr(request, "tenant_id", "") or "").strip()
    return tenant_id or None


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on"}


def _is_enforce_pinned_enabled(request) -> bool:
    effective = get_effective_runtime_setting(
        WORKFLOW_BINDING_ENFORCE_PINNED_KEY,
        _resolve_request_tenant_id(request),
    )
    return _as_bool(effective.value)


def _find_non_pinned_operation_nodes(dag_structure: object) -> list[str]:
    try:
        dag = dag_structure if isinstance(dag_structure, DAGStructure) else DAGStructure(**dag_structure)
    except Exception:
        return []

    node_ids: list[str] = []
    for node in dag.nodes:
        if node.type != "operation":
            continue
        binding_mode = (
            node.operation_ref.binding_mode if node.operation_ref is not None else "alias_latest"
        )
        if binding_mode != "pinned_exposure":
            node_ids.append(node.id)
    return node_ids


def _pinned_policy_error(node_ids: list[str]) -> Response:
    return Response(
        {
            "success": False,
            "error": {
                "code": "TEMPLATE_PIN_REQUIRED",
                "message": (
                    "workflows.operation_binding.enforce_pinned=true requires "
                    "binding_mode='pinned_exposure' for all operation nodes"
                ),
                "details": {"node_ids": node_ids},
            },
        },
        status=400,
    )


def _system_managed_read_only_response() -> Response:
    return Response(
        {
            "success": False,
            "error": {
                "code": WORKFLOW_SYSTEM_MANAGED_READ_ONLY_CODE,
                "message": WORKFLOW_SYSTEM_MANAGED_READ_ONLY_REASON,
            },
        },
        status=409,
    )


def _authoring_boundary_error(violations: list[dict[str, object]]) -> Response:
    return Response(
        {
            "success": False,
            "error": {
                "code": WORKFLOW_AUTHORING_BOUNDARY_VIOLATION_CODE,
                "message": (
                    "Default workflow authoring accepts only analyst-facing constructs. "
                    "Use pinned decision tables for gates; runtime-only nodes and edge-level "
                    "conditions remain compatibility-only."
                ),
                "details": {
                    "violations": violations,
                },
            },
        },
        status=400,
    )

@extend_schema(
    tags=['v2'],
    summary='Create workflow template',
    description='Create a new workflow template. The DAG structure is auto-validated.',
    request=CreateWorkflowRequestSerializer,
    responses={
        201: WorkflowCreateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_workflow(request):
    """
    POST /api/v2/workflows/create-workflow/

    Create a new workflow template.

    Request Body:
        {
            "name": "My Workflow",
            "description": "Optional description",
            "workflow_type": "general",
            "dag_structure": {
                "nodes": [...],
                "edges": [...]
            },
            "is_active": true
        }

    Response (201):
        {
            "workflow": {...},
            "message": "Workflow created successfully"
        }
    """
    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE):
        return _permission_denied("You do not have permission to manage workflows.")

    name = request.data.get('name')
    description = request.data.get('description', '')
    workflow_type = request.data.get('workflow_type', 'general')
    dag_structure = request.data.get('dag_structure')
    is_active = request.data.get('is_active', True)

    # Validate required fields
    if not name:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'name is required'
            }
        }, status=400)

    if not dag_structure:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'dag_structure is required'
            }
        }, status=400)

    authoring_boundary_violations = collect_authoring_boundary_violations(dag_structure)
    if authoring_boundary_violations:
        return _authoring_boundary_error(authoring_boundary_violations)

    if _is_enforce_pinned_enabled(request):
        non_pinned_node_ids = _find_non_pinned_operation_nodes(dag_structure)
        if non_pinned_node_ids:
            return _pinned_policy_error(non_pinned_node_ids)

    try:
        # Create workflow template
        workflow = WorkflowTemplate.objects.create(
            name=name,
            description=description,
            workflow_type=workflow_type,
            dag_structure=dag_structure,
            is_active=is_active,
            created_by=request.user,
        )

        # Auto-validate DAG
        try:
            workflow.validate()
            workflow.save(update_fields=['is_valid'])
        except ValueError as ve:
            # Keep workflow but mark as invalid
            logger.warning(f"Workflow created but validation failed: {ve}")

        serializer = WorkflowTemplateDetailSerializer(workflow)

        logger.info(
            f"Workflow created: {workflow.name} ({workflow.id}) by {request.user.username}"
        )

        return Response({
            'workflow': serializer.data,
            'message': 'Workflow created successfully',
        }, status=201)

    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'CREATE_ERROR',
                'message': str(e)
            }
        }, status=400)


@extend_schema(
    tags=['v2'],
    summary='Update workflow template',
    description='Update an existing workflow template. Supports partial updates. Cannot update if workflow has running executions.',
    request=UpdateWorkflowRequestSerializer,
    responses={
        200: WorkflowUpdateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_workflow(request):
    """
    POST /api/v2/workflows/update-workflow/

    Update an existing workflow template.

    Request Body:
        {
            "workflow_id": "uuid",
            "name": "Updated Name",
            "description": "Updated description",
            "dag_structure": {...},
            "is_active": true
        }

    Response (200):
        {
            "workflow": {...},
            "updated_fields": [...],
            "message": "Workflow updated successfully"
        }
    """
    workflow_id = request.data.get('workflow_id')

    if not workflow_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'workflow_id is required'
            }
        }, status=400)

    try:
        workflow = WorkflowTemplate.objects.get(id=workflow_id)
    except WorkflowTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_NOT_FOUND',
                'message': 'Workflow not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE, workflow):
        return _permission_denied("You do not have permission to manage this workflow.")
    if is_system_managed_workflow(workflow):
        return _system_managed_read_only_response()

    # Check for running executions
    running_count = workflow.executions.filter(
        status__in=[WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]
    ).count()

    if running_count > 0:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_HAS_RUNNING_EXECUTIONS',
                'message': f'Cannot update workflow with {running_count} running execution(s)'
            }
        }, status=409)

    dag_candidate = request.data.get('dag_structure', workflow.dag_structure)

    authoring_boundary_violations = collect_authoring_boundary_violations(dag_candidate)
    if authoring_boundary_violations:
        return _authoring_boundary_error(authoring_boundary_violations)

    if _is_enforce_pinned_enabled(request):
        non_pinned_node_ids = _find_non_pinned_operation_nodes(dag_candidate)
        if non_pinned_node_ids:
            return _pinned_policy_error(non_pinned_node_ids)

    # Track updated fields
    updated_fields = []

    # Update fields if provided
    if 'name' in request.data:
        workflow.name = request.data['name']
        updated_fields.append('name')

    if 'description' in request.data:
        workflow.description = request.data['description']
        updated_fields.append('description')

    if 'workflow_type' in request.data:
        workflow.workflow_type = request.data['workflow_type']
        updated_fields.append('workflow_type')

    if 'is_active' in request.data:
        workflow.is_active = request.data['is_active']
        updated_fields.append('is_active')

    if 'dag_structure' in request.data:
        try:
            workflow.dag_structure = request.data['dag_structure']
        except Exception as exc:
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 'UPDATE_ERROR',
                        'message': str(exc),
                    },
                },
                status=400,
            )
        workflow.is_valid = False  # Mark as needing revalidation
        updated_fields.append('dag_structure')

    try:
        workflow.save()

        # Re-validate if DAG changed
        if 'dag_structure' in request.data:
            try:
                workflow.validate()
                workflow.save(update_fields=['is_valid'])
            except ValueError as ve:
                logger.warning(f"Workflow updated but validation failed: {ve}")

        serializer = WorkflowTemplateDetailSerializer(workflow)

        logger.info(
            f"Workflow updated: {workflow.name} ({workflow.id}) by {request.user.username}, "
            f"fields: {updated_fields}"
        )

        return Response({
            'workflow': serializer.data,
            'updated_fields': updated_fields,
            'message': 'Workflow updated successfully',
        })

    except Exception as e:
        logger.error(f"Failed to update workflow: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'UPDATE_ERROR',
                'message': str(e)
            }
        }, status=400)


@extend_schema(
    tags=['v2'],
    summary='Delete workflow template',
    description='Delete a workflow template (soft delete - deactivates). Use force=true to also cancel running executions.',
    request=DeleteWorkflowRequestSerializer,
    responses={
        200: WorkflowDeleteResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
        500: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_workflow(request):
    """
    POST /api/v2/workflows/delete-workflow/

    Delete a workflow template (soft delete by default).

    Request Body:
        {
            "workflow_id": "uuid",
            "force": false
        }

    Response (200):
        {
            "workflow_id": "uuid",
            "deleted": true,
            "message": "Workflow deleted successfully"
        }
    """
    workflow_id = request.data.get('workflow_id')
    force = request.data.get('force', False)

    if not workflow_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'workflow_id is required'
            }
        }, status=400)

    try:
        workflow = WorkflowTemplate.objects.prefetch_related('executions').get(id=workflow_id)
    except WorkflowTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_NOT_FOUND',
                'message': 'Workflow not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE, workflow):
        return _permission_denied("You do not have permission to manage this workflow.")
    if is_system_managed_workflow(workflow):
        return _system_managed_read_only_response()

    workflow_name = workflow.name

    # Check for running executions
    running_count = workflow.executions.filter(
        status__in=[WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]
    ).count()

    if running_count > 0 and not force:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_HAS_RUNNING_EXECUTIONS',
                'message': f'Cannot delete workflow with {running_count} running execution(s). Use force=true to override.'
            }
        }, status=409)

    try:
        if force:
            # Cancel running executions first
            for execution in workflow.executions.filter(
                status__in=[WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]
            ):
                execution.cancel()
                execution.save()

        # Soft delete - just deactivate
        workflow.is_active = False
        workflow.save(update_fields=['is_active', 'updated_at'])

        logger.info(
            f"Workflow deleted (soft): {workflow_name} ({workflow_id}) by {request.user.username}"
        )

        return Response({
            'workflow_id': str(workflow_id),
            'deleted': True,
            'message': 'Workflow deleted successfully',
        })

    except Exception as e:
        logger.error(f"Failed to delete workflow: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'DELETE_ERROR',
                'message': str(e)
            }
        }, status=500)


@extend_schema(
    tags=['v2'],
    summary='Validate workflow DAG',
    description='Validate a workflow DAG structure. Can validate by workflow_id or by providing dag_structure directly.',
    request=ValidateWorkflowRequestSerializer,
    responses={
        200: WorkflowValidateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_workflow(request):
    """
    POST /api/v2/workflows/validate-workflow/

    Validate a workflow DAG structure.

    Request Body:
        {
            "workflow_id": "uuid"
        }
        OR
        {
            "dag_structure": {...}
        }

    Response (200):
        {
            "valid": true/false,
            "errors": [...],
            "warnings": [...],
            "metadata": {...}
        }
    """
    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE):
        return _permission_denied("You do not have permission to manage workflows.")

    workflow_id = request.data.get('workflow_id')
    dag_structure = request.data.get('dag_structure')

    if not workflow_id and not dag_structure:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'Either workflow_id or dag_structure is required'
            }
        }, status=400)

    try:
        from apps.templates.workflow.validator import DAGValidator
        from apps.templates.workflow.models import DAGStructure

        if workflow_id:
            try:
                workflow = WorkflowTemplate.objects.get(id=workflow_id)
                dag = workflow.dag_structure
            except WorkflowTemplate.DoesNotExist:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'WORKFLOW_NOT_FOUND',
                        'message': 'Workflow not found'
                    }
                }, status=404)
            if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE, workflow):
                return _permission_denied("You do not have permission to manage this workflow.")
            if is_system_managed_workflow(workflow):
                return _system_managed_read_only_response()
        else:
            # Parse dag_structure directly
            try:
                dag = DAGStructure(**dag_structure)
            except Exception as e:
                return Response({
                    'valid': False,
                    'errors': [{
                        'code': 'SCHEMA_ERROR',
                        'message': str(e)
                    }],
                    'warnings': [],
                    'metadata': {}
                })

        # Run DAGValidator
        validator = DAGValidator(dag)
        result = validator.validate()

        def _issue_payload(issue):
            node_ids = list(getattr(issue, "node_ids", []) or [])
            severity = issue.severity.value if hasattr(issue.severity, "value") else issue.severity
            return {
                'code': getattr(issue, "code", "VALIDATION_ERROR"),
                'message': issue.message,
                'node_ids': node_ids,
                'severity': severity,
                'details': getattr(issue, "details", {}) or {},
            }

        # Format errors and warnings
        errors = [_issue_payload(issue) for issue in result.errors]
        warnings = [_issue_payload(issue) for issue in result.warnings]

        # Update workflow is_valid if validating by ID
        if workflow_id and result.is_valid:
            workflow.is_valid = True
            workflow.save(update_fields=['is_valid', 'updated_at'])

        return Response({
            'valid': result.is_valid,
            'errors': errors,
            'warnings': warnings,
            'metadata': result.metadata,
            'topological_order': result.topological_order,
        })

    except Exception as e:
        logger.error(f"Failed to validate workflow: {e}")
        return Response({
            'valid': False,
            'errors': [{
                'code': 'VALIDATION_ERROR',
                'message': str(e)
            }],
            'warnings': [],
            'metadata': {}
        })


@extend_schema(
    tags=['v2'],
    summary='Clone workflow template',
    description='Clone a workflow template. If new_name is provided, creates as new workflow (v1). Otherwise, creates as new version.',
    request=CloneWorkflowRequestSerializer,
    responses={
        201: WorkflowCloneResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clone_workflow(request):
    """
    POST /api/v2/workflows/clone-workflow/

    Clone a workflow template as a new version.

    Request Body:
        {
            "workflow_id": "uuid",
            "new_name": "Optional new name"
        }

    Response (201):
        {
            "workflow": {...},
            "cloned_from": "uuid",
            "message": "Workflow cloned successfully"
        }
    """
    workflow_id = request.data.get('workflow_id')
    new_name = request.data.get('new_name')

    if not workflow_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'workflow_id is required'
            }
        }, status=400)

    try:
        source_workflow = WorkflowTemplate.objects.get(id=workflow_id)
    except WorkflowTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_NOT_FOUND',
                'message': 'Workflow not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE, source_workflow):
        return _permission_denied("You do not have permission to manage this workflow.")
    if is_system_managed_workflow(source_workflow):
        return _system_managed_read_only_response()

    authoring_boundary_violations = collect_authoring_boundary_violations(source_workflow.dag_structure)
    if authoring_boundary_violations:
        return _authoring_boundary_error(authoring_boundary_violations)

    try:
        if new_name:
            # Create with new name (fresh workflow, version 1)
            cloned = WorkflowTemplate.objects.create(
                name=new_name,
                description=source_workflow.description,
                workflow_type=source_workflow.workflow_type,
                dag_structure=source_workflow.dag_structure,
                config=source_workflow.config,
                is_valid=source_workflow.is_valid,
                is_active=True,
                created_by=request.user,
                version_number=1,
            )
        else:
            # Clone as new version (same name, incremented version)
            cloned = source_workflow.clone_as_new_version(created_by=request.user)

        serializer = WorkflowTemplateDetailSerializer(cloned)

        logger.info(
            f"Workflow cloned: {source_workflow.name} ({source_workflow.id}) -> "
            f"{cloned.name} ({cloned.id}) by {request.user.username}"
        )

        return Response({
            'workflow': serializer.data,
            'cloned_from': str(workflow_id),
            'message': 'Workflow cloned successfully',
        }, status=201)

    except Exception as e:
        logger.error(f"Failed to clone workflow: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'CLONE_ERROR',
                'message': str(e)
            }
        }, status=400)


# ============================================================================
# Workflow Execution Endpoints (Phase 4)
# ============================================================================
