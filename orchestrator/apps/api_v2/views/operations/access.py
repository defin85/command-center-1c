"""Operations: access checks for operation streams/details."""

from __future__ import annotations

from apps.databases.models import Database, PermissionLevel
from apps.databases.services import PermissionService
def resolve_operation_access(user, operations):
    allowed = []
    denied = []

    if user.is_staff:
        return [str(op.id) for op in operations], denied

    op_db_ids: dict[str, list[str]] = {}
    all_db_ids: set[str] = set()
    for op in operations:
        db_ids = [str(db.id) for db in op.target_databases.all()]
        op_db_ids[str(op.id)] = db_ids
        all_db_ids.update(db_ids)

    databases = list(
        Database.objects.filter(id__in=all_db_ids)
        .select_related('cluster')
        .only('id', 'cluster_id')
    )
    levels = PermissionService.get_user_levels_for_databases_bulk(user, databases)

    for op in operations:
        op_id = str(op.id)
        db_ids = op_db_ids.get(op_id, [])
        if not db_ids:
            if op.created_by == user.username:
                allowed.append(op_id)
            else:
                denied.append(op_id)
            continue

        has_access = True
        for db_id in db_ids:
            level = levels.get(db_id)
            if level is None or level < PermissionLevel.VIEW:
                has_access = False
                break
        if has_access:
            allowed.append(op_id)
        else:
            denied.append(op_id)

    return allowed, denied
