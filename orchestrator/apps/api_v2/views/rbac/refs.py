"""RBAC endpoints: reference pickers for SPA."""

from __future__ import annotations

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import Cluster, Database
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowTemplate
from apps.artifacts.models import Artifact

from .common import _ensure_manage_rbac, _parse_pagination
from .serializers_core import (
    RefArtifactsResponseSerializer,
    RefClustersResponseSerializer,
    RefDatabasesResponseSerializer,
    RefOperationTemplatesResponseSerializer,
    RefWorkflowTemplatesResponseSerializer,
)

@extend_schema(
    tags=["v2"],
    summary="List clusters (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefClustersResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_clusters(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=1000)

    qs = Cluster.objects.all()
    if search:
        qs = qs.filter(name__icontains=search)

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": row.id, "name": row.name} for row in rows]
    return Response({"clusters": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="List databases (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="cluster_id", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefDatabasesResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_databases(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    cluster_id = (request.query_params.get("cluster_id") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=2000)

    qs = Database.objects.all()
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(id__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": str(row.id), "name": row.name, "cluster_id": row.cluster_id} for row in rows]
    return Response({"databases": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="List operation templates (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefOperationTemplatesResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_operation_templates(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=2000)

    qs = OperationTemplate.objects.all()
    if search:
        qs = qs.filter(Q(id__icontains=search) | Q(name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": row.id, "name": row.name} for row in rows]
    return Response({"templates": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="List workflow templates (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefWorkflowTemplatesResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_workflow_templates(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=2000)

    qs = WorkflowTemplate.objects.all()
    if search:
        qs = qs.filter(name__icontains=search)

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": row.id, "name": row.name} for row in rows]
    return Response({"templates": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="List artifacts (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefArtifactsResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_artifacts(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=2000)

    qs = Artifact.objects.filter(is_deleted=False)
    if search:
        qs = qs.filter(name__icontains=search)

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": row.id, "name": row.name} for row in rows]
    return Response({"artifacts": data, "count": len(data), "total": total})
