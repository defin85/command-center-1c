"""RBAC endpoints: effective access calculation."""

from __future__ import annotations

from typing import Any, Optional

from django.contrib.auth.models import User
from django.db.models import Max, Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import (
    Cluster,
    ClusterGroupPermission,
    ClusterPermission,
    Database,
    DatabaseGroupPermission,
    DatabasePermission,
    PermissionLevel,
)
from apps.templates.models import (
    OperationTemplate,
    OperationTemplateGroupPermission,
    OperationTemplatePermission,
    WorkflowTemplateGroupPermission,
    WorkflowTemplatePermission,
)
from apps.templates.workflow.models import WorkflowTemplate
from apps.artifacts.models import Artifact, ArtifactGroupPermission, ArtifactPermission

from .common import _cluster_ref, _database_ref, _ensure_manage_rbac, _level_code, _parse_pagination, _user_ref
from .serializers_effective_access import EffectiveAccessResponseSerializer

@extend_schema(
    tags=["v2"],
    summary="Get effective access",
    parameters=[
        OpenApiParameter(
            name="user_id",
            type=int,
            required=False,
            description="Optional (default: current user). Requires databases.manage_rbac for other users.",
        ),
        OpenApiParameter(name="include_databases", type=bool, required=False, default=True),
        OpenApiParameter(name="include_clusters", type=bool, required=False, default=True),
        OpenApiParameter(name="include_templates", type=bool, required=False, default=False),
        OpenApiParameter(name="include_workflows", type=bool, required=False, default=False),
        OpenApiParameter(name="include_artifacts", type=bool, required=False, default=False),
        OpenApiParameter(name="limit", type=int, required=False, description="Optional pagination for databases"),
        OpenApiParameter(name="offset", type=int, required=False, description="Optional pagination for databases"),
    ],
    responses={
        200: EffectiveAccessResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_effective_access(request):
    requested_user_id = request.query_params.get("user_id")
    if requested_user_id and int(requested_user_id) != request.user.id:
        denied = _ensure_manage_rbac(request)
        if denied:
            return denied

    target_user = request.user
    if requested_user_id:
        try:
            target_user = User.objects.get(id=requested_user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
                status=404,
            )

    include_clusters = str(request.query_params.get("include_clusters", "true")).lower() != "false"
    include_databases = str(request.query_params.get("include_databases", "true")).lower() != "false"
    include_templates = str(request.query_params.get("include_templates", "false")).lower() == "true"
    include_workflows = str(request.query_params.get("include_workflows", "false")).lower() == "true"
    include_artifacts = str(request.query_params.get("include_artifacts", "false")).lower() == "true"

    use_db_pagination = include_databases and ("limit" in request.query_params or "offset" in request.query_params)
    db_pagination = _parse_pagination(request) if use_db_pagination else None

    direct_cluster_perms = []
    direct_cluster_level_map: dict[str, int] = {}
    direct_cluster_obj_map: dict[str, Cluster] = {}

    if include_clusters or include_databases:
        direct_cluster_perms = list(
            ClusterPermission.objects.select_related("cluster").filter(user=target_user)
        )
        direct_cluster_level_map = {str(p.cluster_id): int(p.level) for p in direct_cluster_perms if p.level is not None}
        direct_cluster_obj_map = {str(p.cluster_id): p.cluster for p in direct_cluster_perms}

    group_cluster_level_map: dict[str, int] = {}
    if include_clusters or include_databases:
        rows = (
            ClusterGroupPermission.objects.filter(group__user=target_user)
            .values("cluster_id")
            .annotate(level=Max("level"))
            .values_list("cluster_id", "level")
        )
        group_cluster_level_map = {str(cluster_id): int(level) for cluster_id, level in rows if level is not None}

    cluster_explicit_level_map: dict[str, int] = {}
    for cluster_id in set(direct_cluster_level_map.keys()).union(group_cluster_level_map.keys()):
        levels = [lvl for lvl in [direct_cluster_level_map.get(cluster_id), group_cluster_level_map.get(cluster_id)] if lvl is not None]
        if levels:
            cluster_explicit_level_map[cluster_id] = max(levels)

    clusters_out = []
    if include_clusters:
        derived_cluster_ids: set[str] = set()
        rows = DatabasePermission.objects.filter(
            user=target_user,
            database__cluster_id__isnull=False,
        ).values_list("database__cluster_id", flat=True)
        derived_cluster_ids.update(str(cid) for cid in rows)

        rows = DatabaseGroupPermission.objects.filter(
            group__user=target_user,
            database__cluster_id__isnull=False,
        ).values_list("database__cluster_id", flat=True)
        derived_cluster_ids.update(str(cid) for cid in rows)

        cluster_ids_to_include = set(cluster_explicit_level_map.keys()).union(derived_cluster_ids)
        cluster_obj_map = dict(direct_cluster_obj_map)
        missing_cluster_ids = [cid for cid in cluster_ids_to_include if cid not in cluster_obj_map]
        if missing_cluster_ids:
            for cluster in Cluster.objects.filter(id__in=missing_cluster_ids).only("id", "name"):
                cluster_obj_map[str(cluster.id)] = cluster

        for cluster_id in sorted(cluster_ids_to_include, key=str):
            cluster = cluster_obj_map.get(cluster_id)
            if cluster is None:
                continue
            level = cluster_explicit_level_map.get(cluster_id)
            if level is None:
                level = PermissionLevel.VIEW
            sources = []
            direct_level = direct_cluster_level_map.get(cluster_id)
            if direct_level is not None:
                sources.append({"source": "direct", "level": _level_code(direct_level)})
            group_level = group_cluster_level_map.get(cluster_id)
            if group_level is not None:
                sources.append({"source": "group", "level": _level_code(group_level)})
            if cluster_id in derived_cluster_ids:
                sources.append({"source": "database", "level": _level_code(PermissionLevel.VIEW)})
            clusters_out.append({"cluster": _cluster_ref(cluster), "level": _level_code(level), "sources": sources})
        clusters_out.sort(key=lambda x: x["cluster"]["name"])

    databases_out = []
    databases_total: Optional[int] = None
    if include_databases:
        direct_db_perms = list(
            DatabasePermission.objects.select_related("database", "database__cluster").filter(user=target_user)
        )
        user_db_level_map: dict[str, int] = {
            str(p.database_id): int(p.level) for p in direct_db_perms if p.level is not None
        }

        rows = (
            DatabaseGroupPermission.objects.filter(group__user=target_user)
            .values("database_id")
            .annotate(level=Max("level"))
            .values_list("database_id", "level")
        )
        group_db_level_map: dict[str, int] = {str(db_id): int(level) for db_id, level in rows if level is not None}

        database_ids_direct = set(user_db_level_map.keys()).union(group_db_level_map.keys())
        cluster_ids_explicit = list(cluster_explicit_level_map.keys())

        qs = Database.objects.select_related("cluster")
        if database_ids_direct or cluster_ids_explicit:
            qs = qs.filter(
                Q(id__in=list(database_ids_direct))
                | Q(cluster_id__in=cluster_ids_explicit)
            )
        else:
            qs = qs.none()

        qs = qs.order_by("name").only("id", "name", "cluster_id")
        if db_pagination is not None:
            databases_total = qs.count()
            qs = qs[db_pagination.offset: db_pagination.offset + db_pagination.limit]
        databases = list(qs)

        for db in databases:
            db_id = str(db.id)
            user_level = user_db_level_map.get(db_id)
            group_level = group_db_level_map.get(db_id)

            direct_level = None
            direct_source = None
            levels_direct = [lvl for lvl in [user_level, group_level] if lvl is not None]
            if levels_direct:
                direct_level = max(levels_direct)
                if user_level is not None and (group_level is None or user_level >= group_level):
                    direct_source = "direct"
                else:
                    direct_source = "group"

            cluster_level = None
            if db.cluster_id:
                cluster_level = cluster_explicit_level_map.get(str(db.cluster_id))

            levels = [lvl for lvl in [direct_level, cluster_level] if lvl is not None]
            if not levels:
                continue
            effective_level = max(levels)
            source = direct_source or "direct"
            via_cluster_id = None
            if cluster_level is not None and (direct_level is None or cluster_level > direct_level):
                source = "cluster"
                via_cluster_id = db.cluster_id

            sources = []
            if user_level is not None:
                sources.append({"source": "direct", "level": _level_code(user_level)})
            if group_level is not None:
                sources.append({"source": "group", "level": _level_code(group_level)})
            if cluster_level is not None:
                sources.append({"source": "cluster", "level": _level_code(cluster_level), "via_cluster_id": db.cluster_id})

            databases_out.append(
                {
                    "database": _database_ref(db),
                    "level": _level_code(effective_level),
                    "source": source,
                    "via_cluster_id": via_cluster_id,
                    "sources": sources,
                }
            )

    operation_templates_out = []
    if include_templates:
        direct_rows = list(
            OperationTemplatePermission.objects.select_related("template").filter(user=target_user)
        )
        direct_level_map: dict[str, int] = {str(p.template_id): int(p.level) for p in direct_rows if p.level is not None}

        group_rows = (
            OperationTemplateGroupPermission.objects.filter(group__user=target_user)
            .values("template_id")
            .annotate(level=Max("level"))
            .values_list("template_id", "level")
        )
        group_level_map: dict[str, int] = {str(tpl_id): int(level) for tpl_id, level in group_rows if level is not None}

        template_ids = set(direct_level_map.keys()).union(group_level_map.keys())
        templates = list(
            OperationTemplate.objects.filter(id__in=list(template_ids)).only("id", "name").order_by("name")
        )
        for tpl in templates:
            tpl_id = str(tpl.id)
            user_level = direct_level_map.get(tpl_id)
            group_level = group_level_map.get(tpl_id)
            levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
            if not levels:
                continue
            effective_level = max(levels)
            source = "direct"
            if group_level is not None and (user_level is None or group_level > user_level):
                source = "group"
            sources = []
            if user_level is not None:
                sources.append({"source": "direct", "level": _level_code(user_level)})
            if group_level is not None:
                sources.append({"source": "group", "level": _level_code(group_level)})
            operation_templates_out.append(
                {"template": {"id": tpl.id, "name": tpl.name}, "level": _level_code(effective_level), "source": source, "sources": sources}
            )

    workflow_templates_out = []
    if include_workflows:
        direct_rows = list(
            WorkflowTemplatePermission.objects.select_related("workflow_template").filter(user=target_user)
        )
        direct_level_map: dict[str, int] = {
            str(p.workflow_template_id): int(p.level) for p in direct_rows if p.level is not None
        }

        group_rows = (
            WorkflowTemplateGroupPermission.objects.filter(group__user=target_user)
            .values("workflow_template_id")
            .annotate(level=Max("level"))
            .values_list("workflow_template_id", "level")
        )
        group_level_map: dict[str, int] = {
            str(tpl_id): int(level) for tpl_id, level in group_rows if level is not None
        }

        template_ids = set(direct_level_map.keys()).union(group_level_map.keys())
        templates = list(
            WorkflowTemplate.objects.filter(id__in=list(template_ids)).only("id", "name").order_by("name")
        )
        for tpl in templates:
            tpl_id = str(tpl.id)
            user_level = direct_level_map.get(tpl_id)
            group_level = group_level_map.get(tpl_id)
            levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
            if not levels:
                continue
            effective_level = max(levels)
            source = "direct"
            if group_level is not None and (user_level is None or group_level > user_level):
                source = "group"
            sources = []
            if user_level is not None:
                sources.append({"source": "direct", "level": _level_code(user_level)})
            if group_level is not None:
                sources.append({"source": "group", "level": _level_code(group_level)})
            workflow_templates_out.append(
                {"template": {"id": tpl.id, "name": tpl.name}, "level": _level_code(effective_level), "source": source, "sources": sources}
            )

    artifacts_out = []
    if include_artifacts:
        direct_rows = list(
            ArtifactPermission.objects.select_related("artifact").filter(user=target_user)
        )
        direct_level_map: dict[str, int] = {str(p.artifact_id): int(p.level) for p in direct_rows if p.level is not None}

        group_rows = (
            ArtifactGroupPermission.objects.filter(group__user=target_user)
            .values("artifact_id")
            .annotate(level=Max("level"))
            .values_list("artifact_id", "level")
        )
        group_level_map: dict[str, int] = {str(art_id): int(level) for art_id, level in group_rows if level is not None}

        artifact_ids = set(direct_level_map.keys()).union(group_level_map.keys())
        artifacts = list(
            Artifact.objects.filter(id__in=list(artifact_ids), is_deleted=False).only("id", "name").order_by("name")
        )
        for art in artifacts:
            art_id = str(art.id)
            user_level = direct_level_map.get(art_id)
            group_level = group_level_map.get(art_id)
            levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
            if not levels:
                continue
            effective_level = max(levels)
            source = "direct"
            if group_level is not None and (user_level is None or group_level > user_level):
                source = "group"
            sources = []
            if user_level is not None:
                sources.append({"source": "direct", "level": _level_code(user_level)})
            if group_level is not None:
                sources.append({"source": "group", "level": _level_code(group_level)})
            artifacts_out.append(
                {"artifact": {"id": art.id, "name": art.name}, "level": _level_code(effective_level), "source": source, "sources": sources}
            )

    response_payload: dict[str, Any] = {
        "user": _user_ref(target_user),
        "clusters": clusters_out,
        "databases": databases_out,
        "operation_templates": operation_templates_out,
        "workflow_templates": workflow_templates_out,
        "artifacts": artifacts_out,
    }
    if db_pagination is not None:
        response_payload["databases_count"] = len(databases_out)
        response_payload["databases_total"] = databases_total or 0
        response_payload["databases_limit"] = db_pagination.limit
        response_payload["databases_offset"] = db_pagination.offset

    return Response(response_payload)
