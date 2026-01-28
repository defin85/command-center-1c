from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .serializers import HealthUpdateSerializer
from .views_common import exclude_schema, logger


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def update_cluster_health(request):
    """
    POST /api/v2/internal/update-cluster-health?cluster_id=X

    Update cluster health status.
    Called by Go Worker after health check execution.

    Query params:
        cluster_id: uuid (required)

    Request body:
    {
        "healthy": true,
        "error_message": "",
        "response_time_ms": 100
    }

    Response:
    {
        "success": true,
        "cluster_id": "...",
        "healthy": true
    }
    """
    from apps.databases.models import Cluster

    cluster_id = request.query_params.get("cluster_id")
    if not cluster_id:
        return Response(
            {"success": False, "error": {"cluster_id": "This query parameter is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = HealthUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        return Response({"success": False, "error": f"Cluster {cluster_id} not found"}, status=status.HTTP_404_NOT_FOUND)

    # Use existing mark_health_check method
    cluster.mark_health_check(success=data["healthy"], error_message=data.get("error_message") if not data["healthy"] else None)

    logger.info(f"Cluster health updated: id={cluster_id}, healthy={data['healthy']}")

    return Response(
        {"success": True, "cluster_id": str(cluster_id), "healthy": data["healthy"]},
        status=status.HTTP_200_OK,
    )

