from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.templates.odata_compatibility_preflight import run_odata_compatibility_preflight


class Command(BaseCommand):
    help = (
        "Run OData compatibility preflight for unified pools publication rollout "
        "using machine-readable profile and schema."
    )

    def add_arguments(self, parser):
        parser.add_argument("--configuration-id", required=True, help="Target configuration_id from profile.")
        parser.add_argument(
            "--compatibility-mode",
            required=False,
            help="Target 1C compatibility mode (e.g. 8.3.23, 8.3.7).",
        )
        parser.add_argument(
            "--write-content-type",
            required=False,
            help="Effective write Content-Type for publication requests.",
        )
        parser.add_argument(
            "--release-profile-version",
            required=False,
            help="Profile version fixed in release artifact.",
        )
        parser.add_argument("--json", action="store_true", help="Print report as JSON.")
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail with non-zero exit code when decision is No-Go.",
        )

    def handle(self, *args, **options):
        as_json = bool(options.get("json"))
        strict = bool(options.get("strict"))
        configuration_id = str(options.get("configuration_id") or "").strip()
        compatibility_mode = options.get("compatibility_mode")
        write_content_type = options.get("write_content_type")
        release_profile_version = options.get("release_profile_version")

        if not configuration_id:
            raise CommandError("configuration-id is required")

        try:
            report = run_odata_compatibility_preflight(
                configuration_id=configuration_id,
                compatibility_mode=compatibility_mode,
                write_content_type=write_content_type,
                release_profile_version=release_profile_version,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        if as_json:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self.stdout.write("odata compatibility preflight report")
            self.stdout.write(f"decision: {report['decision']}")
            self.stdout.write(f"profile_version: {report['profile']['profile_version']}")
            self.stdout.write(f"configuration_id: {report['profile']['configuration_id']}")
            for check in report["checks"]:
                status = "PASS" if check.get("ok") else "FAIL"
                self.stdout.write(f"- {check['key']}: {status}")

        if strict and report.get("decision") != "go":
            raise CommandError("OData compatibility preflight failed: decision=No-Go")
