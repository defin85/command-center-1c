import uuid

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .serializers import HealthUpdateSerializer
from .views_common import exclude_schema, logger


@exclude_schema
@api_view(["GET"])
@permission_classes([IsInternalService])
def get_database_cluster_info(request):
    """
    GET /api/v2/internal/get-database-cluster-info?database_id=X

    Get RAS cluster/infobase identifiers for a database.
    Used as HTTP fallback for worker when Streams are unavailable.

    Query params:
        database_id: string (required)

    Response:
    {
        "success": true,
        "cluster_info": {
            "database_id": "db-123",
            "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
            "infobase_id": "550e8400-e29b-41d4-a716-446655440001",
            "ras_server": "localhost:1545",
            "cluster_user": "",
            "cluster_pwd": ""
        }
    }
    """
    from apps.databases.models import Database

    database_id = request.query_params.get("database_id")
    if not database_id:
        return Response(
            {"success": False, "error": {"database_id": "This query parameter is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        database = Database.objects.select_related("cluster").get(id=database_id)
    except Database.DoesNotExist:
        return Response({"success": False, "error": f"Database {database_id} not found"}, status=status.HTTP_404_NOT_FOUND)

    if not database.cluster:
        return Response(
            {"success": False, "error": {"cluster": "Database has no cluster configured"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cluster = database.cluster
    ras_cluster_uuid = cluster.ras_cluster_uuid or database.ras_cluster_id
    if not ras_cluster_uuid:
        return Response(
            {"success": False, "error": {"ras_cluster_uuid": "RAS cluster metadata is not configured"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    infobase_uuid = database.ras_infobase_id
    if not infobase_uuid:
        try:
            infobase_uuid = uuid.UUID(str(database.id))
        except (ValueError, TypeError, AttributeError):
            infobase_uuid = None
    if not infobase_uuid:
        return Response(
            {"success": False, "error": {"ras_infobase_id": "RAS infobase metadata is not configured"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    infobase_id = str(infobase_uuid)
    ras_server = str(cluster.ras_server) if cluster.ras_server else ""
    cluster_user = str(cluster.cluster_user) if cluster.cluster_user else ""
    cluster_pwd = str(cluster.cluster_pwd) if cluster.cluster_pwd else ""

    return Response(
        {
            "success": True,
            "cluster_info": {
                "database_id": str(database.id),
                "cluster_id": str(ras_cluster_uuid),
                "infobase_id": infobase_id,
                "ras_server": ras_server,
                "cluster_user": cluster_user,
                "cluster_pwd": cluster_pwd,
            },
        },
        status=status.HTTP_200_OK,
    )


@exclude_schema
@api_view(["GET"])
@permission_classes([IsInternalService])
def list_databases_for_health_check(request):
    """
    GET /api/v2/internal/list-databases-for-health-check

    Get list of databases for periodic health checks.
    Called by Go Worker to fetch databases that need health monitoring.

    Response:
    {
        "success": true,
        "databases": [
            {
                "id": "db-123",
                "odata_url": "http://localhost:8080/base/odata/standard.odata",
                "name": "Production DB"
            }
        ],
        "count": 1
    }
    """
    from apps.databases.models import Database

    # Get active databases with OData URL
    databases = (
        Database.objects.filter(status=Database.STATUS_ACTIVE, odata_url__isnull=False)
        .exclude(odata_url="")
        .values("id", "odata_url", "name")
    )

    database_list = [{"id": str(db["id"]), "odata_url": db["odata_url"], "name": db["name"]} for db in databases]

    logger.debug(f"Fetched {len(database_list)} databases for health check")

    return Response(
        {"success": True, "databases": database_list, "count": len(database_list)},
        status=status.HTTP_200_OK,
    )


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def update_database_health(request):
    """
    POST /api/v2/internal/update-database-health?database_id=X

    Update database health status.
    Called by Go Worker after health check execution.

    Query params:
        database_id: uuid (required)

    Request body:
    {
        "healthy": true,
        "error_message": "",
        "response_time_ms": 250,
        "error_code": ""
    }

    Response:
    {
        "success": true,
        "database_id": "...",
        "healthy": true
    }
    """
    from apps.databases.models import Database

    database_id = request.query_params.get("database_id")
    if not database_id:
        return Response(
            {"success": False, "error": {"database_id": "This query parameter is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = HealthUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        database = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response({"success": False, "error": f"Database {database_id} not found"}, status=status.HTTP_404_NOT_FOUND)

    # Use existing mark_health_check method
    database.mark_health_check(success=data["healthy"], response_time=data.get("response_time_ms"))

    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    metadata_updated = False
    if data["healthy"]:
        for key in ("last_health_error", "last_health_error_code"):
            if key in metadata:
                metadata.pop(key, None)
                metadata_updated = True
    else:
        if data.get("error_message"):
            metadata["last_health_error"] = data["error_message"]
            metadata_updated = True
        if data.get("error_code"):
            metadata["last_health_error_code"] = data["error_code"]
            metadata_updated = True

    if metadata_updated:
        database.metadata = metadata
        database.save(update_fields=["metadata", "updated_at"])

    logger.info(f"Database health updated: id={database_id}, healthy={data['healthy']}")

    return Response(
        {"success": True, "database_id": str(database_id), "healthy": data["healthy"]},
        status=status.HTTP_200_OK,
    )

