# Runbook

Статус: authoritative agent-facing guidance.

## Toolchain

Canonical tool versions come from `.tool-versions`:

- Go 1.24.0
- Python 3.13.11
- Node.js 20
- Java temurin-17.0.17+10

## First Local Checks

```bash
bd prime
./debug/runtime-inventory.sh --json
./scripts/dev/health-check.sh
```

## Start And Health

```bash
./scripts/dev/start-all.sh
./scripts/dev/health-check.sh
./debug/probe.sh all
```

## Pool Factual Monitoring

- Quick entry for a fresh session:

```bash
rg -n "preflight_pool_factual_sync" docs/agent/RUNBOOK.md orchestrator/apps/intercompany_pools
alias cc1c-factual-preflight='cd /home/egor/code/command-center-1c/orchestrator && ./venv/bin/python manage.py preflight_pool_factual_sync'
cc1c-factual-preflight --help
```

- `worker-workflows` shipped default path now starts with `ENABLE_GO_SCHEDULER=true`, `ENABLE_POOLOPS_ROUTE=true` and `ENABLE_POOL_PUBLICATION_ODATA_CORE=true` from checked-in env/preset surfaces (`.env.example`, `.env.workflow`, `docker-compose.yml`, `scripts/lib/lifecycle.sh`).
- Active-quarter factual refresh runs through scheduler + workspace default sync; closed-quarter reconcile runs through dedicated nightly scheduler entrypoint on the same `worker-workflows` runtime family.
- Before widening pilot cohort, run factual published-surfaces preflight from Command Center against the target pool/quarter and a bounded set of pilot infobases. The command refreshes metadata through the canonical metadata path and then executes read-only bounded OData probes with the same default factual sync scope.
- Fast sanity checks:

```bash
./scripts/dev/restart.sh worker-workflows
curl -sS http://localhost:9092/health
./debug/eval-django.sh "from apps.intercompany_pools.factual_scheduler_runtime import trigger_pool_factual_active_sync_window; print(trigger_pool_factual_active_sync_window())"
./debug/eval-django.sh \"from apps.intercompany_pools.factual_scheduler_runtime import trigger_pool_factual_closed_quarter_reconcile_window; print(trigger_pool_factual_closed_quarter_reconcile_window())\"
```

- Pilot/preflight gate:

```bash
cd orchestrator && ./venv/bin/python manage.py preflight_pool_factual_sync \
  --pool-id <pool-uuid> \
  --quarter-start 2026-01-01 \
  --requested-by-username <rbac-username-or-empty-when-service-mapping-exists> \
  --database-id <pilot-db-uuid> \
  --database-id <pilot-db-uuid-2> \
  --json \
  --strict
```

- `decision=go` means the cohort passed all mandatory checks: source availability, metadata refresh, required published surfaces, bounded quarter/org/account/movement scope, and live read-only OData probes for the accounting register, information register, and factual documents.
- A checked-in reference bundle for the pilot gate lives at `openspec/changes/archive/2026-03-29-add-pool-factual-balance-monitoring/artifacts/2026-03-29-pilot-preflight-evidence.json`.
- When re-running the gate for another tenant or cohort, save the fresh JSON output next to that reference bundle; repository docs describe the command, but tenant-specific go/no-go still comes from running it on the target pilot infobases.
- Live acceptance for the default path is verified by the shipped sequence `POST /api/v2/pools/batches/ -> GET /api/v2/pools/runs/<run>/report/ -> POST /api/v2/pools/runs/<run>/confirm-publication/ -> GET /api/v2/pools/factual/workspace/`.
- For safe-mode runs, poll the run report until `publication_step_state=completed` or terminal `status=published`; a transient pre-projection snapshot is not the acceptance point.
- A checked-in live acceptance snapshot lives at `openspec/changes/archive/2026-03-29-add-pool-factual-balance-monitoring/artifacts/2026-03-29-live-default-path-evidence.md`.
- Factual acceptance is not complete unless the workspace summary surfaces explicit `backlog_total` / staleness in the operator freshness card, not only source availability.
- Default operator producer path starts in `/pools/runs` with `Create canonical batch`, not with manual batch UUID entry.
- Run-to-factual handoff must preserve `quarter_start`, because the factual workspace uses it to land on the intended settlement quarter rather than the latest pool snapshot.
- Default verification for a receipt cohort is: create batch, confirm publication, open `/pools/factual`, then verify `summary.backlog_total`, `summary.freshness_state`, and `review_queue.summary` before widening the cohort.
- Manual late correction closure is verified through `POST /api/v2/pools/factual/review-actions/` with `action=reconcile`; attributable items use `action=attribute`.

- Operator-facing route:

```bash
printf '%s\n' "http://localhost:15173/pools/factual?pool=<pool-uuid>"
printf '%s\n' "http://localhost:15173/pools/factual?pool=<pool-uuid>&quarter_start=2026-01-01&focus=settlement&detail=1"
```

- Default operator producer path for factual acceptance:
  open `http://localhost:15173/pools/runs?pool=<pool-uuid>` and use the `Create canonical batch` drawer on the create stage. Receipt intake creates the canonical batch and opens the linked inspect/run context without manual batch UUID entry.

## Runtime Control

| Runtime | Start / Restart | Health | Eval |
|---|---|---|---|
| `orchestrator` | `./scripts/dev/restart.sh orchestrator` | `http://localhost:8200/health` | `./debug/eval-django.sh "print('ok')"` |
| `event-subscriber` | `./scripts/dev/restart.sh event-subscriber` | `process-only (pids/event-subscriber.pid)` | `./debug/eval-django.sh "from apps.operations.models import BatchOperation; print(BatchOperation.objects.count())"` |
| `api-gateway` | `./scripts/dev/restart.sh api-gateway` | `http://localhost:8180/health` | `delve via ./scripts/dev/debug-service.sh api-gateway 2345` |
| `worker` | `./scripts/dev/restart.sh worker` | `http://localhost:9191/health` | `delve via ./scripts/dev/debug-service.sh worker 2346` |
| `worker-workflows` | `./scripts/dev/restart.sh worker-workflows` | `http://localhost:9092/health` | `delve via ./scripts/dev/debug-service.sh worker 2346` |
| `frontend` | `./scripts/dev/restart.sh frontend` | `http://localhost:15173` | `./debug/eval-frontend.sh "document.title"` |

## Debug Toolkit

- Runtime inventory: `./debug/runtime-inventory.sh`
- Runtime probes: `./debug/probe.sh all`
- Runtime restart + probe: `./debug/restart-runtime.sh <runtime>`
- Django eval: `./debug/eval-django.sh "<python code>"`
- Frontend eval: `./debug/eval-frontend.sh "<js expression>"`

## Repo Tooling Surfaces

- Codex project config: `.codex/config.toml`
- OpenSpec context: `openspec/project.md`
- Root repo contract: `AGENTS.md`
- Frontend scripts source: `frontend/package.json`
- Dev scripts: `scripts/dev/*`

## When To Use Supplemental Docs

- `README.md` — broader human-readable project overview
- `DEBUG.md` — detailed live-debug and incident recipes
- `scripts/dev/README.md` — long-form notes on dev scripts
