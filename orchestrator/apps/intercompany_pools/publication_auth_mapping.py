from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.databases.models import InfobaseUserMapping

from .models import OrganizationPool, PoolNodeVersion


PUBLICATION_AUTH_STRATEGY_ACTOR = "actor"
PUBLICATION_AUTH_STRATEGY_SERVICE = "service"

ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED = "ODATA_MAPPING_NOT_CONFIGURED"
ERROR_CODE_ODATA_MAPPING_AMBIGUOUS = "ODATA_MAPPING_AMBIGUOUS"
ERROR_CODE_ODATA_PUBLICATION_AUTH_CONTEXT_INVALID = "ODATA_PUBLICATION_AUTH_CONTEXT_INVALID"

RESOLUTION_OUTCOME_ACTOR_SUCCESS = "actor_success"
RESOLUTION_OUTCOME_SERVICE_SUCCESS = "service_success"
RESOLUTION_OUTCOME_MISSING_MAPPING = "missing_mapping"
RESOLUTION_OUTCOME_AMBIGUOUS_MAPPING = "ambiguous_mapping"
RESOLUTION_OUTCOME_INVALID_AUTH_CONTEXT = "invalid_auth_context"


@dataclass(frozen=True)
class PublicationAuthCoverage:
    strategy: str
    actor_username: str
    target_database_ids: tuple[str, ...]
    missing_database_ids: tuple[str, ...]
    ambiguous_database_ids: tuple[str, ...]
    incomplete_database_ids: tuple[str, ...]
    invalid_context: str | None = None

    @property
    def has_gaps(self) -> bool:
        return bool(
            self.invalid_context
            or self.missing_database_ids
            or self.ambiguous_database_ids
            or self.incomplete_database_ids
        )

    @property
    def resolution_outcome(self) -> str:
        if self.invalid_context:
            return RESOLUTION_OUTCOME_INVALID_AUTH_CONTEXT
        if self.ambiguous_database_ids:
            return RESOLUTION_OUTCOME_AMBIGUOUS_MAPPING
        if self.missing_database_ids or self.incomplete_database_ids:
            return RESOLUTION_OUTCOME_MISSING_MAPPING
        if self.strategy == PUBLICATION_AUTH_STRATEGY_ACTOR:
            return RESOLUTION_OUTCOME_ACTOR_SUCCESS
        return RESOLUTION_OUTCOME_SERVICE_SUCCESS


def resolve_pool_target_database_ids(
    *,
    pool: OrganizationPool,
    target_date: date,
) -> tuple[str, ...]:
    database_ids = (
        PoolNodeVersion.objects.filter(pool=pool, effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .exclude(organization__database_id__isnull=True)
        .values_list("organization__database_id", flat=True)
        .distinct()
    )
    return tuple(sorted(str(database_id) for database_id in database_ids))


def evaluate_publication_auth_coverage(
    *,
    pool: OrganizationPool,
    target_date: date,
    strategy: str,
    actor_username: str = "",
) -> PublicationAuthCoverage:
    normalized_strategy = str(strategy or "").strip().lower()
    normalized_actor_username = str(actor_username or "").strip()
    target_database_ids = resolve_pool_target_database_ids(pool=pool, target_date=target_date)

    if normalized_strategy not in {
        PUBLICATION_AUTH_STRATEGY_ACTOR,
        PUBLICATION_AUTH_STRATEGY_SERVICE,
    }:
        return PublicationAuthCoverage(
            strategy=normalized_strategy,
            actor_username=normalized_actor_username,
            target_database_ids=target_database_ids,
            missing_database_ids=(),
            ambiguous_database_ids=(),
            incomplete_database_ids=(),
            invalid_context="publication_auth.strategy must be actor|service",
        )

    if not target_database_ids:
        return PublicationAuthCoverage(
            strategy=normalized_strategy,
            actor_username=normalized_actor_username,
            target_database_ids=(),
            missing_database_ids=(),
            ambiguous_database_ids=(),
            incomplete_database_ids=(),
        )

    mappings_by_database: dict[str, list[InfobaseUserMapping]] = defaultdict(list)
    if normalized_strategy == PUBLICATION_AUTH_STRATEGY_ACTOR:
        if not normalized_actor_username:
            return PublicationAuthCoverage(
                strategy=normalized_strategy,
                actor_username=normalized_actor_username,
                target_database_ids=target_database_ids,
                missing_database_ids=target_database_ids,
                ambiguous_database_ids=(),
                incomplete_database_ids=(),
                invalid_context="publication_auth.actor_username is required for actor strategy",
            )
        user_model = get_user_model()
        actor_user = user_model.objects.filter(username=normalized_actor_username).only("id").first()
        if actor_user is None:
            return PublicationAuthCoverage(
                strategy=normalized_strategy,
                actor_username=normalized_actor_username,
                target_database_ids=target_database_ids,
                missing_database_ids=target_database_ids,
                ambiguous_database_ids=(),
                incomplete_database_ids=(),
            )
        mapping_queryset = InfobaseUserMapping.objects.filter(
            database_id__in=target_database_ids,
            user=actor_user,
        )
    else:
        mapping_queryset = InfobaseUserMapping.objects.filter(
            database_id__in=target_database_ids,
            is_service=True,
            user__isnull=True,
        )

    for mapping in mapping_queryset.only("database_id", "ib_username", "ib_password"):
        mappings_by_database[str(mapping.database_id)].append(mapping)

    missing_database_ids: list[str] = []
    ambiguous_database_ids: list[str] = []
    incomplete_database_ids: list[str] = []
    for database_id in target_database_ids:
        candidates = mappings_by_database.get(database_id, [])
        if not candidates:
            missing_database_ids.append(database_id)
            continue
        if len(candidates) > 1:
            ambiguous_database_ids.append(database_id)
            continue
        mapping = candidates[0]
        if not str(mapping.ib_username or "").strip() or not str(mapping.ib_password or "").strip():
            incomplete_database_ids.append(database_id)

    return PublicationAuthCoverage(
        strategy=normalized_strategy,
        actor_username=normalized_actor_username,
        target_database_ids=target_database_ids,
        missing_database_ids=tuple(sorted(missing_database_ids)),
        ambiguous_database_ids=tuple(sorted(ambiguous_database_ids)),
        incomplete_database_ids=tuple(sorted(incomplete_database_ids)),
    )


def build_publication_auth_fail_closed_error(
    coverage: PublicationAuthCoverage,
) -> tuple[str, str]:
    remediation = "Configure Infobase Users in /rbac."
    if coverage.invalid_context:
        return (
            ERROR_CODE_ODATA_PUBLICATION_AUTH_CONTEXT_INVALID,
            f"{coverage.invalid_context}. {remediation}",
        )
    if coverage.ambiguous_database_ids:
        return (
            ERROR_CODE_ODATA_MAPPING_AMBIGUOUS,
            (
                "Ambiguous infobase mapping for publication auth context: "
                f"target_database_ids={_format_database_ids(coverage.ambiguous_database_ids)}. "
                f"{remediation}"
            ),
        )
    missing_like = tuple(
        sorted(
            set(coverage.missing_database_ids).union(set(coverage.incomplete_database_ids))
        )
    )
    if missing_like:
        return (
            ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
            (
                "Infobase mapping is not configured for publication auth context: "
                f"target_database_ids={_format_database_ids(missing_like)}. "
                f"{remediation}"
            ),
        )
    return "", ""


def _format_database_ids(database_ids: Iterable[str]) -> str:
    return ",".join(sorted(str(database_id) for database_id in database_ids))
