## 1. CI orchestration
- [ ] 1.1 Выбрать и зафиксировать целевую CI платформу для репозитория (GitHub Actions / GitLab CI / Jenkins).
- [ ] 1.2 Добавить обязательный job `contract-gates` с последовательным запуском:
  - `./contracts/scripts/build-orchestrator-openapi.sh check`
  - `./contracts/scripts/validate-specs.sh`
  - `./contracts/scripts/check-breaking-changes.sh`
- [ ] 1.3 Настроить job как блокирующий merge/promotion (без `allow_failure`).

## 2. Tooling and environment
- [ ] 2.1 Обеспечить установку required tooling в CI образе (`oasdiff`, OpenAPI validator, Node/npm или `redocly` для bundle-check).
- [ ] 2.2 Зафиксировать запуск gate-скриптов в CI-контексте (`CI=true`) без fallback-послаблений.

## 3. Documentation
- [ ] 3.1 Обновить `contracts/README.md` разделом о CI contract gates (что запускается, где смотреть логи, как чинить типовые падения).
- [ ] 3.2 Добавить короткий runbook для команды: действия при падении `bundle check`, `validate`, `breaking changes`.

## 4. Validation
- [ ] 4.1 Прогнать dry-run/тестовый запуск CI job и зафиксировать артефакты прохождения.
- [ ] 4.2 Прогнать `openspec validate add-ci-contract-gates-pipeline --strict --no-interactive`.
