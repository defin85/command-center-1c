from django.core.management.base import BaseCommand, CommandError

from apps.operations.services.runtime_control import execute_runtime_action_run


class Command(BaseCommand):
    help = "Execute a persisted runtime-control action run."

    def add_arguments(self, parser):
        parser.add_argument("--action-run-id", required=True)

    def handle(self, *args, **options):
        action_run_id = str(options["action_run_id"] or "").strip()
        if not action_run_id:
            raise CommandError("--action-run-id is required")

        action_run = execute_runtime_action_run(action_run_id)
        self.stdout.write(
            self.style.SUCCESS(f"Runtime action {action_run.id} finished with status={action_run.status}")
        )
