from __future__ import annotations

import json
from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.databases.models import Database
from apps.intercompany_pools.models import OrganizationPool
from apps.intercompany_pools.publication_auth_mapping import (
    PUBLICATION_AUTH_STRATEGY_ACTOR,
    PUBLICATION_AUTH_STRATEGY_SERVICE,
    evaluate_publication_auth_coverage,
    resolve_pool_target_database_ids,
)


class Command(BaseCommand):
    help = (
        "Run preflight coverage checks for pool publication OData auth mapping "
        "(RBAC Infobase Users)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--pool-id",
            type=str,
            default="",
            help="Filter by a single pool id.",
        )
        parser.add_argument(
            "--tenant-id",
            type=str,
            default="",
            help="Filter by tenant id.",
        )
        parser.add_argument(
            "--period-date",
            type=str,
            default="",
            help="Reference period date in YYYY-MM-DD (defaults to today).",
        )
        parser.add_argument(
            "--strategy",
            choices=["actor", "service", "both"],
            default="both",
            help="Mapping strategy coverage to validate.",
        )
        parser.add_argument(
            "--actor-username",
            type=str,
            default="",
            help="Actor username for actor strategy coverage checks.",
        )
        parser.add_argument(
            "--include-inactive-pools",
            action="store_true",
            help="Include inactive pools in coverage.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print report as JSON.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail with non-zero exit code on no-go decision.",
        )

    def handle(self, *args: Any, **options: Any):
        strategy_mode = str(options.get("strategy") or "both").strip().lower()
        actor_username = str(options.get("actor_username") or "").strip()
        if strategy_mode in {"actor", "both"} and not actor_username:
            raise CommandError("--actor-username is required when strategy includes actor.")

        period_date = self._parse_period_date(str(options.get("period_date") or "").strip())
        report = self._build_report(
            pool_id=str(options.get("pool_id") or "").strip(),
            tenant_id=str(options.get("tenant_id") or "").strip(),
            include_inactive_pools=bool(options.get("include_inactive_pools")),
            period_date=period_date,
            strategy_mode=strategy_mode,
            actor_username=actor_username,
        )

        if bool(options.get("json")):
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self._print_human_report(report)

        if bool(options.get("strict")) and report["decision"] != "go":
            raise CommandError(
                "Pool publication auth mapping preflight failed: "
                f"decision={report['decision']}, total_critical_mismatches="
                f"{report['summary']['total_critical_mismatches']}."
            )

    def _parse_period_date(self, raw_value: str) -> date:
        if not raw_value:
            return date.today()
        try:
            return date.fromisoformat(raw_value)
        except ValueError as exc:
            raise CommandError("--period-date must be in YYYY-MM-DD format.") from exc

    def _build_report(
        self,
        *,
        pool_id: str,
        tenant_id: str,
        include_inactive_pools: bool,
        period_date: date,
        strategy_mode: str,
        actor_username: str,
    ) -> dict[str, Any]:
        pools_qs = OrganizationPool.objects.all().order_by("code", "id")
        if tenant_id:
            pools_qs = pools_qs.filter(tenant_id=tenant_id)
        if pool_id:
            pools_qs = pools_qs.filter(id=pool_id)
        if not include_inactive_pools:
            pools_qs = pools_qs.filter(is_active=True)

        pools = list(pools_qs.only("id", "code", "tenant_id", "is_active"))
        strategy_list: list[str]
        if strategy_mode == "both":
            strategy_list = [PUBLICATION_AUTH_STRATEGY_ACTOR, PUBLICATION_AUTH_STRATEGY_SERVICE]
        else:
            strategy_list = [strategy_mode]

        actor_missing: set[str] = set()
        actor_ambiguous: set[str] = set()
        actor_incomplete: set[str] = set()
        actor_invalid_context = 0

        service_missing: set[str] = set()
        service_ambiguous: set[str] = set()
        service_incomplete: set[str] = set()
        service_invalid_context = 0

        pooled_target_databases: set[str] = set()
        pool_reports: list[dict[str, Any]] = []

        for pool in pools:
            target_database_ids = resolve_pool_target_database_ids(
                pool=pool,
                target_date=period_date,
            )
            pooled_target_databases.update(target_database_ids)
            pool_report: dict[str, Any] = {
                "pool_id": str(pool.id),
                "pool_code": pool.code,
                "tenant_id": str(pool.tenant_id),
                "is_active": bool(pool.is_active),
                "target_database_ids": list(target_database_ids),
            }

            if PUBLICATION_AUTH_STRATEGY_ACTOR in strategy_list:
                actor_coverage = evaluate_publication_auth_coverage(
                    pool=pool,
                    target_date=period_date,
                    strategy=PUBLICATION_AUTH_STRATEGY_ACTOR,
                    actor_username=actor_username,
                )
                pool_report["actor"] = self._coverage_to_dict(actor_coverage)
                actor_missing.update(actor_coverage.missing_database_ids)
                actor_ambiguous.update(actor_coverage.ambiguous_database_ids)
                actor_incomplete.update(actor_coverage.incomplete_database_ids)
                if actor_coverage.invalid_context:
                    actor_invalid_context += 1

            if PUBLICATION_AUTH_STRATEGY_SERVICE in strategy_list:
                service_coverage = evaluate_publication_auth_coverage(
                    pool=pool,
                    target_date=period_date,
                    strategy=PUBLICATION_AUTH_STRATEGY_SERVICE,
                )
                pool_report["service"] = self._coverage_to_dict(service_coverage)
                service_missing.update(service_coverage.missing_database_ids)
                service_ambiguous.update(service_coverage.ambiguous_database_ids)
                service_incomplete.update(service_coverage.incomplete_database_ids)
                if service_coverage.invalid_context:
                    service_invalid_context += 1

            pool_reports.append(pool_report)

        legacy_candidate_ids = sorted(
            actor_missing.union(actor_incomplete).union(service_missing).union(service_incomplete)
        )
        legacy_credentials_only = sorted(
            str(database_id)
            for database_id in Database.objects.filter(
                id__in=legacy_candidate_ids,
            )
            .exclude(username__exact="")
            .exclude(password__exact="")
            .values_list("id", flat=True)
        )

        checks = [
            self._check(
                key="actor_mapping_missing",
                description="Actor mapping must exist for target databases.",
                mismatches=len(actor_missing),
                critical=PUBLICATION_AUTH_STRATEGY_ACTOR in strategy_list,
                details={"database_ids": sorted(actor_missing)},
            ),
            self._check(
                key="actor_mapping_ambiguous",
                description="Actor mapping must be deterministic (single match per target database).",
                mismatches=len(actor_ambiguous),
                critical=PUBLICATION_AUTH_STRATEGY_ACTOR in strategy_list,
                details={"database_ids": sorted(actor_ambiguous)},
            ),
            self._check(
                key="actor_mapping_incomplete",
                description="Actor mapping must contain non-empty username/password.",
                mismatches=len(actor_incomplete),
                critical=PUBLICATION_AUTH_STRATEGY_ACTOR in strategy_list,
                details={"database_ids": sorted(actor_incomplete)},
            ),
            self._check(
                key="actor_auth_context_invalid",
                description="Actor auth context must be valid for preflight.",
                mismatches=int(actor_invalid_context),
                critical=PUBLICATION_AUTH_STRATEGY_ACTOR in strategy_list,
                details={"invalid_pool_count": int(actor_invalid_context)},
            ),
            self._check(
                key="service_mapping_missing",
                description="Service mapping must exist for target databases.",
                mismatches=len(service_missing),
                critical=PUBLICATION_AUTH_STRATEGY_SERVICE in strategy_list,
                details={"database_ids": sorted(service_missing)},
            ),
            self._check(
                key="service_mapping_ambiguous",
                description="Service mapping must be deterministic (single match per target database).",
                mismatches=len(service_ambiguous),
                critical=PUBLICATION_AUTH_STRATEGY_SERVICE in strategy_list,
                details={"database_ids": sorted(service_ambiguous)},
            ),
            self._check(
                key="service_mapping_incomplete",
                description="Service mapping must contain non-empty username/password.",
                mismatches=len(service_incomplete),
                critical=PUBLICATION_AUTH_STRATEGY_SERVICE in strategy_list,
                details={"database_ids": sorted(service_incomplete)},
            ),
            self._check(
                key="service_auth_context_invalid",
                description="Service auth context must be valid for preflight.",
                mismatches=int(service_invalid_context),
                critical=PUBLICATION_AUTH_STRATEGY_SERVICE in strategy_list,
                details={"invalid_pool_count": int(service_invalid_context)},
            ),
            self._check(
                key="legacy_credentials_only",
                description=(
                    "Databases with legacy Database.username/password but without valid mapping "
                    "require backfill to /rbac."
                ),
                mismatches=len(legacy_credentials_only),
                critical=False,
                details={"database_ids": legacy_credentials_only},
            ),
        ]
        total_critical_mismatches = sum(
            int(item["mismatches"]) for item in checks if bool(item["critical"])
        )
        decision = "go" if total_critical_mismatches == 0 else "no_go"

        return {
            "generated_at": date.today().isoformat(),
            "period_date": period_date.isoformat(),
            "strategy_mode": strategy_mode,
            "actor_username": actor_username,
            "decision": decision,
            "summary": {
                "pools_total": len(pools),
                "target_databases_total": len(pooled_target_databases),
                "total_checks": len(checks),
                "total_critical_mismatches": total_critical_mismatches,
            },
            "checks": checks,
            "pools": pool_reports,
        }

    def _check(
        self,
        *,
        key: str,
        description: str,
        mismatches: int,
        critical: bool,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "key": key,
            "description": description,
            "mismatches": int(mismatches),
            "critical": bool(critical),
            "status": "pass" if int(mismatches) == 0 else "fail",
            "details": details,
        }

    def _coverage_to_dict(self, coverage) -> dict[str, Any]:
        return {
            "strategy": coverage.strategy,
            "actor_username": coverage.actor_username,
            "target_database_ids": list(coverage.target_database_ids),
            "missing_database_ids": list(coverage.missing_database_ids),
            "ambiguous_database_ids": list(coverage.ambiguous_database_ids),
            "incomplete_database_ids": list(coverage.incomplete_database_ids),
            "invalid_context": coverage.invalid_context,
            "resolution_outcome": coverage.resolution_outcome,
        }

    def _print_human_report(self, report: dict[str, Any]) -> None:
        self.stdout.write("pool publication auth mapping preflight report")
        self.stdout.write(f"generated_at: {report['generated_at']}")
        self.stdout.write(f"period_date: {report['period_date']}")
        self.stdout.write(f"decision: {report['decision']}")
        self.stdout.write(f"strategy_mode: {report['strategy_mode']}")
        if report.get("actor_username"):
            self.stdout.write(f"actor_username: {report['actor_username']}")
        summary = report["summary"]
        self.stdout.write(f"pools_total: {summary['pools_total']}")
        self.stdout.write(f"target_databases_total: {summary['target_databases_total']}")
        self.stdout.write(f"total_critical_mismatches: {summary['total_critical_mismatches']}")
        for check in report.get("checks") or []:
            self.stdout.write(
                f"- [{check['status']}] key={check['key']} "
                f"critical={check['critical']} mismatches={check['mismatches']}"
            )
