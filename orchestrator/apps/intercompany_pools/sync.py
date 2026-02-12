from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.databases.models import Database
from apps.tenancy.models import Tenant

from .models import Organization, OrganizationStatus


@dataclass(frozen=True)
class OrganizationSyncStats:
    created: int
    updated: int
    skipped: int


def sync_organizations(tenant: Tenant, rows: Iterable[Mapping[str, Any]]) -> OrganizationSyncStats:
    created = 0
    updated = 0
    skipped = 0

    with transaction.atomic():
        for index, row in enumerate(rows):
            normalized = _normalize_row(row, index=index)
            database = _resolve_database(tenant=tenant, database_id=normalized["database_id"], index=index)
            organization = Organization.objects.filter(tenant=tenant, inn=normalized["inn"]).first()
            _validate_database_link_uniqueness(
                tenant=tenant,
                database=database,
                index=index,
                current_organization=organization,
            )

            if organization is None:
                Organization.objects.create(
                    tenant=tenant,
                    database=database,
                    name=normalized["name"],
                    full_name=normalized["full_name"],
                    inn=normalized["inn"],
                    kpp=normalized["kpp"],
                    status=normalized["status"],
                    external_ref=normalized["external_ref"],
                    metadata=normalized["metadata"],
                )
                created += 1
                continue

            changed_fields = _collect_changed_fields(organization=organization, normalized=normalized, database=database)
            if not changed_fields:
                skipped += 1
                continue

            for field_name, value in changed_fields.items():
                setattr(organization, field_name, value)
            organization.save(update_fields=[*changed_fields.keys(), "updated_at"])
            updated += 1

    return OrganizationSyncStats(created=created, updated=updated, skipped=skipped)


def _normalize_row(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise ValidationError(f"sync row #{index} must be an object")

    inn = str(row.get("inn") or "").strip()
    if not inn:
        raise ValidationError(f"sync row #{index} must provide inn")

    name = str(row.get("name") or "").strip()
    if not name:
        raise ValidationError(f"sync row #{index} must provide name")

    status = str(row.get("status") or OrganizationStatus.ACTIVE).strip().lower()
    if status not in OrganizationStatus.values:
        raise ValidationError(
            f"sync row #{index} has unknown status '{status}', allowed: {', '.join(OrganizationStatus.values)}"
        )

    metadata = row.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, Mapping):
        raise ValidationError(f"sync row #{index} metadata must be an object")

    database_id_raw = row.get("database_id")
    database_id = str(database_id_raw).strip() if database_id_raw is not None else None
    if database_id == "":
        database_id = None

    return {
        "inn": inn,
        "name": name,
        "full_name": str(row.get("full_name") or "").strip(),
        "kpp": str(row.get("kpp") or "").strip(),
        "status": status,
        "external_ref": str(row.get("external_ref") or "").strip(),
        "metadata": dict(metadata),
        "database_id": database_id,
    }


def _resolve_database(tenant: Tenant, database_id: str | None, index: int) -> Database | None:
    if not database_id:
        return None

    database = Database.objects.filter(tenant=tenant, id=database_id).first()
    if database is None:
        raise ValidationError(
            f"sync row #{index} references unknown database_id '{database_id}' for tenant '{tenant.slug}'"
        )
    return database


def _collect_changed_fields(
    organization: Organization,
    normalized: dict[str, Any],
    database: Database | None,
) -> dict[str, Any]:
    changed: dict[str, Any] = {}

    fields_to_compare = {
        "database": database,
        "name": normalized["name"],
        "full_name": normalized["full_name"],
        "kpp": normalized["kpp"],
        "status": normalized["status"],
        "external_ref": normalized["external_ref"],
        "metadata": normalized["metadata"],
    }
    for field_name, new_value in fields_to_compare.items():
        current_value = getattr(organization, field_name)
        if current_value != new_value:
            changed[field_name] = new_value

    return changed


def _validate_database_link_uniqueness(
    tenant: Tenant,
    database: Database | None,
    index: int,
    current_organization: Organization | None,
) -> None:
    if database is None:
        return

    conflict_qs = Organization.objects.filter(tenant=tenant, database=database)
    if current_organization is not None:
        conflict_qs = conflict_qs.exclude(pk=current_organization.pk)

    if conflict_qs.exists():
        raise ValidationError(
            f"sync row #{index} tries to rebind database '{database.id}' "
            f"that is already linked to another organization"
        )
