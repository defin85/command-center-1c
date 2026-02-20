"""Operations endpoint: execute_ibcmd_cli_operation."""

from __future__ import annotations


from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated

from .execute_ibcmd_cli_impl import _execute_ibcmd_cli_validated
from .schemas import (
    ExecuteIbcmdCliOperationRequestSerializer,
    ExecuteIbcmdCliOperationThrottle,
    ExecuteOperationResponseSerializer,
    OperationErrorResponseSerializer,
)

@extend_schema(
    tags=['v2'],
    summary='Execute schema-driven IBCMD command (ibcmd_cli)',
    description='''
    Queue schema-driven IBCMD command for execution.

    Uses driver catalog v2 (base@approved + overrides@active) to validate `command_id`
    and build canonical `argv[]`.

    Supports both scopes:
    - per_database: executes per selected database
    - global: executes once (requires `auth_database_id` for RBAC + IB user mapping)

    Dangerous commands require `confirm_dangerous=true`.
    ''',
    request=ExecuteIbcmdCliOperationRequestSerializer,
    responses={
        202: ExecuteOperationResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        409: OpenApiResponse(description='Conflict'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExecuteIbcmdCliOperationThrottle])
def execute_ibcmd_cli_operation(request):
    serializer = ExecuteIbcmdCliOperationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return _execute_ibcmd_cli_validated(request, serializer.validated_data)


