from __future__ import annotations

from dataclasses import dataclass, field

from .models import Organization, PoolMasterParty


REMEDIATION_REASON_NO_MATCH = "no_match"
REMEDIATION_REASON_AMBIGUOUS_MATCH = "ambiguous_match"
REMEDIATION_REASON_CANDIDATE_ALREADY_BOUND = "candidate_already_bound"


@dataclass(frozen=True)
class OrganizationPartyBindingRemediationItem:
    organization_id: str
    tenant_id: str
    inn: str
    kpp: str
    reason: str
    candidate_party_ids: tuple[str, ...]
    candidate_party_canonical_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "organization_id": self.organization_id,
            "tenant_id": self.tenant_id,
            "inn": self.inn,
            "kpp": self.kpp,
            "reason": self.reason,
            "candidate_party_ids": list(self.candidate_party_ids),
            "candidate_party_canonical_ids": list(self.candidate_party_canonical_ids),
        }


@dataclass
class OrganizationPartyBindingBackfillStats:
    organizations_scanned: int = 0
    organizations_already_bound: int = 0
    organizations_bound: int = 0
    organizations_unresolved_no_match: int = 0
    organizations_unresolved_ambiguous: int = 0
    organizations_unresolved_candidate_already_bound: int = 0
    remediation_list: list[OrganizationPartyBindingRemediationItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "organizations_scanned": self.organizations_scanned,
            "organizations_already_bound": self.organizations_already_bound,
            "organizations_bound": self.organizations_bound,
            "organizations_unresolved_no_match": self.organizations_unresolved_no_match,
            "organizations_unresolved_ambiguous": self.organizations_unresolved_ambiguous,
            "organizations_unresolved_candidate_already_bound": self.organizations_unresolved_candidate_already_bound,
            "remediation_count": len(self.remediation_list),
            "remediation_list": [item.to_dict() for item in self.remediation_list],
        }


def run_organization_party_binding_backfill() -> OrganizationPartyBindingBackfillStats:
    stats = OrganizationPartyBindingBackfillStats()
    bound_party_ids = {
        str(value)
        for value in Organization.objects.exclude(master_party_id__isnull=True).values_list("master_party_id", flat=True)
    }

    organizations = Organization.objects.select_related("master_party").order_by(
        "tenant_id",
        "inn",
        "kpp",
        "id",
    )
    for organization in organizations.iterator():
        stats.organizations_scanned += 1
        if organization.master_party_id is not None:
            stats.organizations_already_bound += 1
            continue

        candidates = _find_candidates_for_organization(organization=organization)
        if not candidates:
            stats.organizations_unresolved_no_match += 1
            _append_remediation(
                stats=stats,
                organization=organization,
                reason=REMEDIATION_REASON_NO_MATCH,
                candidates=[],
            )
            continue

        if len(candidates) > 1:
            stats.organizations_unresolved_ambiguous += 1
            _append_remediation(
                stats=stats,
                organization=organization,
                reason=REMEDIATION_REASON_AMBIGUOUS_MATCH,
                candidates=candidates,
            )
            continue

        candidate = candidates[0]
        candidate_id = str(candidate.id)
        if candidate_id in bound_party_ids:
            stats.organizations_unresolved_candidate_already_bound += 1
            _append_remediation(
                stats=stats,
                organization=organization,
                reason=REMEDIATION_REASON_CANDIDATE_ALREADY_BOUND,
                candidates=candidates,
            )
            continue

        organization.master_party_id = candidate.id
        organization.full_clean()
        organization.save(update_fields=["master_party", "updated_at"])
        bound_party_ids.add(candidate_id)
        stats.organizations_bound += 1

    return stats


def _find_candidates_for_organization(*, organization: Organization) -> list[PoolMasterParty]:
    inn = str(organization.inn or "").strip()
    if not inn:
        return []

    candidates = PoolMasterParty.objects.filter(
        tenant_id=organization.tenant_id,
        inn=inn,
        is_our_organization=True,
    )
    kpp = str(organization.kpp or "").strip()
    if kpp:
        candidates = candidates.filter(kpp=kpp)

    return list(candidates.order_by("canonical_id", "id"))


def _append_remediation(
    *,
    stats: OrganizationPartyBindingBackfillStats,
    organization: Organization,
    reason: str,
    candidates: list[PoolMasterParty],
) -> None:
    stats.remediation_list.append(
        OrganizationPartyBindingRemediationItem(
            organization_id=str(organization.id),
            tenant_id=str(organization.tenant_id),
            inn=str(organization.inn or ""),
            kpp=str(organization.kpp or ""),
            reason=reason,
            candidate_party_ids=tuple(str(item.id) for item in candidates),
            candidate_party_canonical_ids=tuple(str(item.canonical_id) for item in candidates),
        )
    )
