# Go Services Guidance

- Scope: `go-services/` contains the Go API Gateway and Worker binaries plus shared packages.
- First read:
  - `docs/agent/VERIFY.md`
  - `docs/agent/RUNBOOK.md`
  - `openspec/project.md`
- Entry points:
  - `go-services/api-gateway/cmd/main.go`
  - `go-services/worker/cmd/main.go`
  - `go-services/shared/`
- Local constraints:
  - prefer project build and restart scripts over ad-hoc `go run`
  - keep private code under service-local packages; shared code belongs only in `go-services/shared/`
  - use `./scripts/dev/debug-service.sh` or `./debug/runtime-inventory.sh --json` for runtime debug entry points
- Canonical validation commands:
  - `./scripts/dev/lint.sh --go`
  - `cd go-services/api-gateway && go test ./...`
  - `cd go-services/worker && go test ./...`

