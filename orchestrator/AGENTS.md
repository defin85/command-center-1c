# Orchestrator Guidance

- Scope: `orchestrator/` contains the Django Orchestrator, domain apps and Channels/DRF integration.
- First read:
  - `docs/agent/TASK_ROUTING.md`
  - `docs/agent/DOMAIN_MAP.md`
  - `docs/agent/VERIFY.md`
  - `docs/agent/RUNBOOK.md`
  - `openspec/project.md`
- Entry points:
  - `orchestrator/config/asgi.py`
  - `orchestrator/manage.py`
  - `orchestrator/apps/`
- Local constraints:
  - use `orchestrator/venv` through project scripts; do not assume global Python
  - keep Django apps isolated; avoid speculative cross-app imports
  - use `./debug/eval-django.sh` for short runtime evaluation
- Canonical validation commands:
  - `./scripts/dev/lint.sh --python`
  - `./scripts/dev/pytest.sh -q <path>`
