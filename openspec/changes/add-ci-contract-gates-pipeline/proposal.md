# Change: Обязательные CI contract gates для OpenAPI tooling

## Why
После change `refactor-orchestrator-openapi-modularization` в репозитории уже есть необходимые скрипты проверки контрактов (`build/check`, validate, breaking changes), но CI pipeline пока отсутствует.

Из-за этого обязательные проверки выполняются только локально (pre-commit/dev workflow), что оставляет риск пропуска регрессий при интеграции изменений в общий поток разработки.

Нужно зафиксировать отдельный change как технический долг на подключение этих проверок в будущий CI.

## What Changes
- Добавить обязательный CI job для контрактов с последовательным запуском:
  - `./contracts/scripts/build-orchestrator-openapi.sh check`
  - `./contracts/scripts/validate-specs.sh`
  - `./contracts/scripts/check-breaking-changes.sh`
- Зафиксировать fail-fast семантику: любой сбой contract gate должен переводить job в `failed`.
- Зафиксировать требование к окружению CI: `CI=true` и наличие обязательных инструментов проверки.
- Обновить эксплуатационную документацию после подключения CI.

## Impact
- Affected specs:
  - `api-contract-ci-gates` (new)
- Affected code (expected, when implementing this change):
  - CI pipeline config (GitHub Actions / GitLab CI / Jenkinsfile в зависимости от выбранной платформы)
  - `contracts/scripts/validate-specs.sh` (используется как strict validator gate)
  - `contracts/scripts/check-breaking-changes.sh` (используется как breaking-change gate)
  - `contracts/scripts/build-orchestrator-openapi.sh` (используется как drift-check gate)
  - `contracts/README.md` (документация CI-режима)

## Non-Goals
- Изменение API-семантики в `contracts/orchestrator/openapi.yaml` или `contracts/orchestrator/src/**`.
- Изменение существующих бизнес-эндпоинтов, схем или generated clients в рамках этого change.
- Замена текущих локальных pre-commit/dev проверок.

## Assumptions
- CI platform будет выбрана отдельно (репозиторий пока не содержит CI-конфигурации).
- Скрипты contract gates, уже присутствующие в репозитории, остаются источником истины для проверок.
