# Change: Модульная структура OpenAPI для orchestrator с bundle в единый контракт

## Why
`contracts/orchestrator/openapi.yaml` разросся до большого монолитного файла, который сложно сопровождать: растут риски merge-конфликтов, ошибок YAML и длительного цикла правок даже для локальных изменений схем/эндпоинтов.

При этом текущий toolchain проекта ожидает единый файл `contracts/orchestrator/openapi.yaml` как вход для validate/codegen/route generation. Нужен безопасный переход к модульным исходникам без слома существующего pipeline.

## What Changes
- Ввести модульную структуру исходников OpenAPI для orchestrator (разделение `paths` и `components` на доменные файлы под `contracts/orchestrator/src/**`).
- Добавить обязательный bundle-step, который собирает модульные исходники в единый артефакт `contracts/orchestrator/openapi.yaml`.
- Обновить contract tooling (`validate-specs.sh`, `generate-all.sh`, `check-breaking-changes.sh`) так, чтобы он работал через собранный bundle и не ломался на относительных `$ref`.
- Добавить проверку "source -> bundle не устарел" для локального workflow и CI.
- Обновить документацию по редактированию контрактов и отладке проблем bundle/refs.
- API-семантика НЕ меняется: change затрагивает структуру хранения и процесс сборки контракта.

## Impact
- Affected specs:
  - `api-contract-modularization`
- Affected code (high-level):
  - `contracts/orchestrator/openapi.yaml`
  - `contracts/orchestrator/src/**` (new)
  - `contracts/scripts/validate-specs.sh`
  - `contracts/scripts/generate-all.sh`
  - `contracts/scripts/check-breaking-changes.sh`
  - `contracts/README.md`
  - `docs/QUICKSTART_OPENAPI.md`
  - `docs/OPENAPI_CONTRACT_CHECKLIST.md`

## Non-Goals
- Добавление/удаление endpoint-ов, параметров и бизнес-логики API.
- Введение новой версии API.
- Изменение внешних контрактов клиентов из-за этого change (кроме тех, что реально уже были в исходниках).
