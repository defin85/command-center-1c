## 0. Подготовка
- [x] 0.1 Зафиксировать список Go файлов >700 строк (по правилам из `add-file-size-guideline-700`).
- [x] 0.2 Согласовать схему именования файлов внутри пакетов (`*_handlers.go`, `*_types.go`, `*_helpers.go` и т.п.).

## 1. Разнос драйверов/очередей
- [x] 1.1 `ibcmdops/driver.go`: выделить подфайлы по группам ответственности (build argv, resolve creds, execute, types).
- [x] 1.2 `stream_consumer.go`: выделить обработку событий/ack/retry/metrics в отдельные файлы внутри пакета.

## 2. Разнос saga/orchestrator
- [x] 2.1 `saga/orchestrator.go`: разделить на файлы (core state machine, handlers, persistence, helpers).
- [x] 2.2 `saga/types.go`: разделить на доменные типы/DTO/ошибки.

## 3. Тесты
- [x] 3.1 Разнести `*_test.go` файлы >700 строк на несколько файлов (по сценариям), сохранив читаемость.
- [x] 3.2 Проверить, что интеграционные тесты остаются стабильными (по возможности — группировать по темам).

## 4. Валидация
- [x] 4.1 `go test ./...` (релевантные модули/полный прогон по договорённости)
- [x] 4.2 `./scripts/dev/lint.sh` (если включает Go проверки) — `golangci-lint` требует установки в окружении; `make lint-go` выявляет существующие ошибки в `go-services/api-gateway` (errcheck/staticcheck).
- [x] 4.3 `openspec validate refactor-go-files-under-700 --strict --no-interactive`
