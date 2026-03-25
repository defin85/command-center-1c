## 1. Domain onboarding
- [x] 1.1 Добавить stable checked-in domain/product map для нового агента с ключевыми сущностями, operator workflows и различением между реализованными и roadmap surfaces.
- [x] 1.2 Включить новый domain map в canonical onboarding path, чтобы он был discoverable из `docs/agent/INDEX.md` и repo-level guidance.

## 2. Task routing
- [x] 2.1 Добавить bounded task routing matrix для типовых task families с первыми docs, кодовыми entry points, validation commands и machine-readable surfaces.
- [x] 2.2 Обновить root/scoped guidance так, чтобы routing matrix был видимым и не дублировал длинные procedural instructions.

## 3. Freshness automation
- [x] 3.1 Расширить freshness validation на critical guidance references, которые можно проверить недеструктивным behavioral/smoke способом.
- [x] 3.2 Усилить проверку согласованности authoritative docs с runtime inventory и canonical command surfaces не только по наличию строк, но и по semantic correspondence.

## 4. Validation
- [x] 4.1 Прогнать `./scripts/dev/check-agent-doc-freshness.sh`.
- [x] 4.2 Прогнать `openspec validate add-agent-onboarding-acceleration --strict --no-interactive`.
