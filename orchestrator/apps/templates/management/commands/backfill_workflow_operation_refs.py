from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.templates.workflow.models import DAGStructure, WorkflowTemplate


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _strip_nones(value: object) -> object:
    if isinstance(value, dict):
        return {k: _strip_nones(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_nones(item) for item in value]
    return value


class Command(BaseCommand):
    help = (
        "Backfill workflow DAG operation bindings (template_id -> operation_ref) "
        "using deterministic schema normalization."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyze and report changes without persisting updates.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print result stats as JSON.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        as_json = bool(options.get("json"))

        scanned = 0
        changed = 0
        updated = 0
        unchanged = 0
        errors = 0

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT id, dag_structure FROM workflow_templates")
                    rows = cursor.fetchall()

                for workflow_id, raw_dag in rows:
                    scanned += 1
                    if isinstance(raw_dag, dict):
                        raw_dict = raw_dag
                    elif isinstance(raw_dag, str):
                        try:
                            parsed = json.loads(raw_dag)
                        except json.JSONDecodeError:
                            parsed = {}
                        raw_dict = parsed if isinstance(parsed, dict) else {}
                    else:
                        raw_dict = {}
                    try:
                        canonical_dag = DAGStructure(**raw_dict).model_dump(
                            by_alias=True,
                            exclude_none=True,
                        )
                    except Exception as exc:
                        errors += 1
                        self.stderr.write(
                            self.style.ERROR(
                                f"workflow_id={workflow_id} schema_error={exc}"
                            )
                        )
                        continue

                    raw_normalized = _strip_nones(raw_dict)
                    canonical_normalized = _strip_nones(canonical_dag)

                    if _stable_json(raw_normalized) == _stable_json(canonical_normalized):
                        unchanged += 1
                        continue

                    changed += 1
                    if not dry_run:
                        WorkflowTemplate.objects.filter(id=workflow_id).update(dag_structure=canonical_dag)
                        updated += 1

                payload = {
                    "scanned": scanned,
                    "changed": changed,
                    "updated": updated,
                    "unchanged": unchanged,
                    "errors": errors,
                    "dry_run": dry_run,
                }

                if as_json:
                    self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    self.stdout.write(self.style.SUCCESS("Workflow operation_ref backfill finished"))
                    for key, value in payload.items():
                        self.stdout.write(f"{key}: {value}")

                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("DRY RUN: transaction rolled back"))

        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Workflow tables are unavailable. Run migrations first: `python manage.py migrate`."
            ) from exc
