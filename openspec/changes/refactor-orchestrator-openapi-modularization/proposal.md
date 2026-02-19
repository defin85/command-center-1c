# Change: Модульная структура OpenAPI для orchestrator с bundle в единый контракт

## Why
`contracts/orchestrator/openapi.yaml` стал крупным монолитом, из-за чего растут риски merge-конфликтов, ошибок YAML и длительного цикла review даже для локальных правок.

При этом текущие потребители контракта жёстко завязаны на единый файл `contracts/orchestrator/openapi.yaml`:
- валидация (`contracts/scripts/validate-specs.sh`);
- генерация маршрутов/клиентов (`contracts/scripts/generate-all.sh`, `frontend/orval.config.ts`);
- contract parity тесты (`orchestrator/apps/api_v2/tests/*openapi*`).

Нужна модульная структура source-файлов без потери совместимости с текущим pipeline.

## What Changes
- Закрепить `contracts/orchestrator/src/**` как единственный editable source-of-truth для public OpenAPI orchestrator.
- Стандартизовать bundle pipeline на одном инструменте (`Redocly CLI`) и собирать детерминированный `contracts/orchestrator/openapi.yaml`.
- Добавить отдельный шаг сборки/проверки актуальности bundle (`build` + `check`) с fail-fast диагностикой.
- Обновить `validate-specs.sh`, `generate-all.sh`, `check-breaking-changes.sh` на bundle-first workflow.
- Убрать неявное перезаписывание `contracts/orchestrator/openapi.yaml` через `manage.py spectacular` из обычного generate workflow; экспорт из Django оставить только явной ручной операцией.
- Усилить quality gates для локальной разработки и CI: drift-check source->bundle, строгая OpenAPI-валидация, корректный breaking-check по bundle.
- Обновить документацию (`contracts/README.md`, `docs/QUICKSTART_OPENAPI.md`, `docs/OPENAPI_CONTRACT_CHECKLIST.md`) под новый процесс.
- API-семантика НЕ меняется: change затрагивает хранение и процесс сборки контракта.

## Impact
- Affected specs:
  - `api-contract-modularization`
- Affected code (high-level):
  - `contracts/orchestrator/openapi.yaml`
  - `contracts/orchestrator/src/**` (new)
  - `contracts/scripts/build-orchestrator-openapi.sh` (new)
  - `contracts/scripts/validate-specs.sh`
  - `contracts/scripts/generate-all.sh`
  - `contracts/scripts/check-breaking-changes.sh`
  - `contracts/scripts/export-django-openapi.sh`
  - `.githooks/pre-commit`
  - `scripts/dev/start-all.sh`
  - `contracts/README.md`
  - `docs/QUICKSTART_OPENAPI.md`
  - `docs/OPENAPI_CONTRACT_CHECKLIST.md`

## Non-Goals
- Добавление/удаление endpoint-ов, параметров и бизнес-логики API.
- Введение новой версии API.
- Переход на OpenAPI 3.1 в рамках этого change.
- Изменение внешних контрактов клиентов из-за этой миграции (кроме уже существующих изменений в исходниках).
