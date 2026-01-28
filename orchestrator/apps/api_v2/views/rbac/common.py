"""RBAC shared helpers (API v2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from django.contrib.auth.models import Group, User
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.databases.models import Cluster, Database, PermissionLevel

def _ensure_manage_rbac(request):
    if request.user.has_perm(perms.PERM_DATABASES_MANAGE_RBAC):
        return None
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": "Forbidden"}},
        status=403,
    )

def _user_ref(user: Optional[User]) -> Optional[dict]:
    if user is None:
        return None
    return {"id": user.id, "username": user.username}


def _group_ref(group: Optional[Group]) -> Optional[dict]:
    if group is None:
        return None
    return {"id": group.id, "name": group.name}


def _cluster_ref(cluster: Cluster) -> dict:
    return {"id": cluster.id, "name": cluster.name}


def _database_ref(database: Database) -> dict:
    return {"id": str(database.id), "name": database.name, "cluster_id": database.cluster_id}

def _level_code(level: Optional[int]) -> Optional[str]:
    if level is None:
        return None
    try:
        return PermissionLevel(int(level)).name
    except Exception:
        return None


@dataclass(frozen=True)
class _Pagination:
    limit: int
    offset: int


def _parse_pagination(request, default_limit: int = 50, max_limit: int = 200) -> _Pagination:
    try:
        limit = int(request.query_params.get("limit", default_limit))
    except Exception:
        limit = default_limit
    try:
        offset = int(request.query_params.get("offset", 0))
    except Exception:
        offset = 0
    limit = max(1, min(limit, max_limit))
    offset = max(0, offset)
    return _Pagination(limit=limit, offset=offset)


def _dedupe_keep_order(items: list[Any]) -> list[Any]:
    return list(dict.fromkeys(items))


def _bulk_upsert_group_permissions(
    *,
    model,
    group: Group,
    object_ids: list[Any],
    object_id_field: str,
    level: int,
    notes: str,
    granted_by: User,
) -> dict[str, int]:
    ids = _dedupe_keep_order(object_ids)
    if not ids:
        return {"created": 0, "updated": 0, "skipped": 0, "total": 0}

    existing_rows = list(
        model.objects.select_for_update().filter(group=group, **{f"{object_id_field}__in": ids})
    )
    existing_map = {getattr(row, object_id_field): row for row in existing_rows}

    to_create = []
    to_update = []

    created = 0
    updated = 0
    skipped = 0

    for object_id in ids:
        row = existing_map.get(object_id)
        if row is None:
            to_create.append(
                model(
                    group=group,
                    **{
                        object_id_field: object_id,
                        "level": level,
                        "notes": notes,
                        "granted_by": granted_by,
                    },
                )
            )
            created += 1
            continue

        changed = False
        if row.level is None or int(row.level) != int(level):
            row.level = level
            changed = True
        if (row.notes or "") != notes:
            row.notes = notes
            changed = True
        if row.granted_by_id != granted_by.id:
            row.granted_by = granted_by
            changed = True

        if changed:
            to_update.append(row)
            updated += 1
        else:
            skipped += 1

    if to_create:
        model.objects.bulk_create(to_create, batch_size=1000)
    if to_update:
        model.objects.bulk_update(to_update, ["level", "notes", "granted_by"])

    return {"created": created, "updated": updated, "skipped": skipped, "total": len(ids)}


def _bulk_delete_group_permissions(
    *,
    model,
    group: Group,
    object_ids: list[Any],
    object_id_field: str,
) -> dict[str, int]:
    ids = _dedupe_keep_order(object_ids)
    if not ids:
        return {"deleted": 0, "skipped": 0, "total": 0}

    qs = model.objects.filter(group=group, **{f"{object_id_field}__in": ids})
    existing_count = qs.count()
    qs.delete()
    deleted = existing_count
    skipped = len(ids) - deleted
    return {"deleted": deleted, "skipped": skipped, "total": len(ids)}



