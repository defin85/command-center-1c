# Команды (must-know)

- Запуск/стоп: `./scripts/dev/start-all.sh`, `./scripts/dev/stop-all.sh`.
- Перезапуск/логи: `./scripts/dev/restart.sh <svc>` (`--help`), `./scripts/dev/logs.sh <svc>`.
- Здоровье/линт: `./scripts/dev/health-check.sh`, `./scripts/dev/lint.sh` (или `--fix`).
- Контракты: `./contracts/scripts/validate-specs.sh`, `./contracts/scripts/generate-all.sh`.

Примечание: `make test` может быть docker-ориентирован.
