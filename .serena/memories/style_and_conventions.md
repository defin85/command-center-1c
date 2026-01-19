# Стиль и конвенции (ядро)

- API: contract-first (`contracts/**/openapi.yaml` → validate → generate), v2 `/api/v2/*`, `snake_case`.
- Маршрутизация: frontend → только Gateway (8180).
- Go: `gofmt -s`, минимум `go vet`, тесты `go test ./...`.
- Python: тесты `pytest`, линт `ruff` (единый вход — `./scripts/dev/lint.sh`).
- Frontend: `tsc --noEmit`, `eslint`.
