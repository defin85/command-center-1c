## 1. Модульная структура OpenAPI исходников
- [ ] 1.1 Определить target layout `contracts/orchestrator/src/**` (корневой файл, разбиение `paths` и `components` по доменам).
- [ ] 1.2 Перенести содержимое текущего `contracts/orchestrator/openapi.yaml` в модульные файлы без изменения API-семантики.
- [ ] 1.3 Зафиксировать соглашения по именованию и размещению модулей (чтобы новые endpoints добавлялись в правильный модуль).

## 2. Bundle-пайплайн
- [ ] 2.1 Добавить скрипт сборки модульных исходников в единый `contracts/orchestrator/openapi.yaml`.
- [ ] 2.2 Обеспечить детерминированный output bundle (стабильный порядок, повторяемый результат).
- [ ] 2.3 Добавить команду/режим для проверки, что bundle актуален относительно `src/**`.

## 3. Интеграция с validate/codegen/breaking-check
- [ ] 3.1 Обновить `contracts/scripts/validate-specs.sh`: валидировать собранный bundle и корректно падать при неактуальном bundle.
- [ ] 3.2 Обновить `contracts/scripts/generate-all.sh`: использовать bundle как единственный вход для генераторов.
- [ ] 3.3 Обновить `contracts/scripts/check-breaking-changes.sh`: сравнивать bundle-to-bundle, чтобы относительные `$ref` не ломали проверку.

## 4. Документация и эксплуатация
- [ ] 4.1 Обновить `contracts/README.md` новым workflow (`edit src -> bundle -> validate -> generate`).
- [ ] 4.2 Обновить `docs/QUICKSTART_OPENAPI.md` и `docs/OPENAPI_CONTRACT_CHECKLIST.md` с примерами нового процесса.
- [ ] 4.3 Добавить troubleshooting секцию для ошибок bundle/refs.

## 5. Верификация
- [ ] 5.1 Прогнать `./contracts/scripts/validate-specs.sh` после миграции на modular source.
- [ ] 5.2 Прогнать `./contracts/scripts/generate-all.sh` и проверить отсутствие регрессий в generated artifacts.
- [ ] 5.3 Прогнать `openspec validate refactor-orchestrator-openapi-modularization --strict --no-interactive`.
