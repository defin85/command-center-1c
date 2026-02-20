#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--json" ]]; then
  cat <<'JSON'
[
  {
    "runtime": "orchestrator",
    "type": "backend",
    "stack": "python/django/daphne",
    "entrypoint": "orchestrator/config/asgi.py",
    "start": "./scripts/dev/restart.sh orchestrator",
    "health": "http://localhost:8200/health",
    "eval": "./debug/eval-django.sh \"print('ok')\"",
    "tests": "./scripts/dev/pytest.sh -q <path>"
  },
  {
    "runtime": "event-subscriber",
    "type": "worker",
    "stack": "python/django-management-command",
    "entrypoint": "orchestrator/manage.py run_event_subscriber",
    "start": "./scripts/dev/restart.sh event-subscriber",
    "health": "process-only (pids/event-subscriber.pid)",
    "eval": "./debug/eval-django.sh \"from apps.operations.models import BatchOperation; print(BatchOperation.objects.count())\"",
    "tests": "./scripts/dev/pytest.sh -q orchestrator/apps/operations/tests"
  },
  {
    "runtime": "api-gateway",
    "type": "backend",
    "stack": "go/gin",
    "entrypoint": "go-services/api-gateway/cmd/main.go",
    "start": "./scripts/dev/restart.sh api-gateway",
    "health": "http://localhost:8180/health",
    "eval": "delve via ./scripts/dev/debug-service.sh api-gateway 2345",
    "tests": "cd go-services/api-gateway && go test ./..."
  },
  {
    "runtime": "worker",
    "type": "worker",
    "stack": "go",
    "entrypoint": "go-services/worker/cmd/main.go",
    "start": "./scripts/dev/restart.sh worker",
    "health": "http://localhost:9191/health",
    "eval": "delve via ./scripts/dev/debug-service.sh worker 2346",
    "tests": "cd go-services/worker && go test ./..."
  },
  {
    "runtime": "worker-workflows",
    "type": "worker",
    "stack": "go (same binary, different stream)",
    "entrypoint": "go-services/worker/cmd/main.go",
    "start": "./scripts/dev/restart.sh worker-workflows",
    "health": "http://localhost:9092/health",
    "eval": "delve via ./scripts/dev/debug-service.sh worker 2346",
    "tests": "cd go-services/worker && go test ./..."
  },
  {
    "runtime": "frontend",
    "type": "frontend",
    "stack": "react/vite",
    "entrypoint": "frontend/src/main.tsx",
    "start": "./scripts/dev/restart.sh frontend",
    "health": "http://localhost:15173",
    "eval": "./debug/eval-frontend.sh \"document.title\"",
    "tests": "cd frontend && npm run test:run -- <path>"
  }
]
JSON
  exit 0
fi

cat <<'TXT'
Runtime Inventory (CommandCenter1C)
==================================

1) orchestrator
   - type: backend (python/django/daphne)
   - entrypoint: orchestrator/config/asgi.py
   - start: ./scripts/dev/restart.sh orchestrator
   - health: http://localhost:8200/health
   - eval: ./debug/eval-django.sh "print('ok')"
   - tests: ./scripts/dev/pytest.sh -q <path>

2) event-subscriber
   - type: worker (python management command)
   - entrypoint: orchestrator/manage.py run_event_subscriber
   - start: ./scripts/dev/restart.sh event-subscriber
   - health: process-only (pids/event-subscriber.pid)
   - eval: ./debug/eval-django.sh "from apps.operations.models import BatchOperation; print(BatchOperation.objects.count())"
   - tests: ./scripts/dev/pytest.sh -q orchestrator/apps/operations/tests

3) api-gateway
   - type: backend (go/gin)
   - entrypoint: go-services/api-gateway/cmd/main.go
   - start: ./scripts/dev/restart.sh api-gateway
   - health: http://localhost:8180/health
   - eval: delve via ./scripts/dev/debug-service.sh api-gateway 2345
   - tests: cd go-services/api-gateway && go test ./...

4) worker
   - type: worker (go)
   - entrypoint: go-services/worker/cmd/main.go
   - start: ./scripts/dev/restart.sh worker
   - health: http://localhost:9191/health
   - eval: delve via ./scripts/dev/debug-service.sh worker 2346
   - tests: cd go-services/worker && go test ./...

5) worker-workflows
   - type: worker (go, workflows stream)
   - entrypoint: go-services/worker/cmd/main.go
   - start: ./scripts/dev/restart.sh worker-workflows
   - health: http://localhost:9092/health
   - eval: delve via ./scripts/dev/debug-service.sh worker 2346
   - tests: cd go-services/worker && go test ./...

6) frontend
   - type: frontend (react/vite)
   - entrypoint: frontend/src/main.tsx
   - start: ./scripts/dev/restart.sh frontend
   - health: http://localhost:15173
   - eval: ./debug/eval-frontend.sh "document.title"
   - tests: cd frontend && npm run test:run -- <path>
TXT

