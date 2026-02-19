## 1. Архитектурная фиксация и модульный layout
- [ ] 1.1 Зафиксировать `contracts/orchestrator/src/**` как единственный editable source-of-truth и описать naming conventions модулей.
- [ ] 1.2 Подготовить target layout (`root`, `paths/**`, `components/**`) и правила добавления новых endpoint/schema.
- [ ] 1.3 Перенести текущее содержимое `contracts/orchestrator/openapi.yaml` в модульные source-файлы без изменения API-семантики.

## 2. Bundle pipeline (Redocly CLI)
- [ ] 2.1 Добавить script для сборки bundle (например, `contracts/scripts/build-orchestrator-openapi.sh`) и стандартизовать на `Redocly CLI`.
- [ ] 2.2 Реализовать режимы `build` и `check` (drift-check source->bundle с fail-fast ошибкой).
- [ ] 2.3 Обеспечить детерминированный output: повторный build без изменения `src/**` не меняет `contracts/orchestrator/openapi.yaml`.

## 3. Интеграция с существующим tooling и quality gates
- [ ] 3.1 Обновить `contracts/scripts/validate-specs.sh`: сначала проверка актуальности bundle, затем валидация собранного контракта.
- [ ] 3.2 Обновить `contracts/scripts/generate-all.sh`: использовать bundle как единственный вход для генераторов и убрать неявный runtime export из стандартного потока.
- [ ] 3.3 Обновить `contracts/scripts/check-breaking-changes.sh`: сравнивать bundle-to-bundle; в CI отсутствие `oasdiff` считать ошибкой.
- [ ] 3.4 Обновить `.githooks/pre-commit` и dev workflow (`scripts/dev/start-all.sh`) для обязательного drift-check перед validate/generate.

## 4. Документация и эксплуатация
- [ ] 4.1 Обновить `contracts/README.md` workflow до `edit src -> build/check bundle -> validate -> generate`.
- [ ] 4.2 Обновить `docs/QUICKSTART_OPENAPI.md` и `docs/OPENAPI_CONTRACT_CHECKLIST.md` под модульный процесс.
- [ ] 4.3 Добавить troubleshooting для ошибок `$ref`, drift-check, и случаев отсутствия validator/oasdiff.
- [ ] 4.4 Явно задокументировать: `export-django-openapi.sh` это manual operation, не default источник публичного контракта.

## 5. Верификация и критерии приёмки
- [ ] 5.1 Прогнать `./contracts/scripts/validate-specs.sh` после миграции.
- [ ] 5.2 Прогнать `./contracts/scripts/generate-all.sh` и проверить отсутствие регрессий в generated artifacts.
- [ ] 5.3 Прогнать `./contracts/scripts/check-breaking-changes.sh` на изменениях контракта.
- [ ] 5.4 Прогнать parity-тесты `orchestrator/apps/api_v2/tests/test_pool_runs_openapi_contract_parity.py` и `orchestrator/apps/api_v2/tests/test_pool_runs_generated_client_parity.py`.
- [ ] 5.5 Прогнать `openspec validate refactor-orchestrator-openapi-modularization --strict --no-interactive`.
