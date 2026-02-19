## Context
Текущий orchestrator-контракт хранится в одном файле `contracts/orchestrator/openapi.yaml` (~19k строк). Это усложняет параллельную работу и повышает риск нецелевых изменений при merge.

При этом контракт уже является критическим интеграционным артефактом:
- `contracts/scripts/validate-specs.sh` и `contracts/scripts/check-breaking-changes.sh` работают по `contracts/orchestrator/openapi.yaml`;
- `contracts/scripts/generate-all.sh` генерирует proxy routes для API gateway из `contracts/orchestrator/openapi.yaml`;
- `frontend/orval.config.ts` генерирует frontend-клиент из `contracts/orchestrator/openapi.yaml`;
- parity-тесты в `orchestrator/apps/api_v2/tests/*openapi*` проверяют контракт и generated artifacts.

Значит, в целевой архитектуре нужно разделить source-файлы, но сохранить единый delivery artifact.

## Goals / Non-Goals
- Goals:
  - Перейти на модульные OpenAPI source-файлы в `contracts/orchestrator/src/**`.
  - Сохранить совместимый единый bundle `contracts/orchestrator/openapi.yaml`.
  - Сделать процесс детерминированным и fail-fast по drift `src -> bundle`.
  - Устранить неявные перезаписи bundle из альтернативных pipeline шагов.
- Non-Goals:
  - Менять API-поведение или публичные контракты endpoint-ов в рамках этой миграции.
  - Переводить проект на OpenAPI 3.1.
  - Полностью переписывать contract tooling с нуля.

## Architecture Drivers
- Совместимость: downstream tooling и тесты уже завязаны на единый `openapi.yaml`.
- Надёжность: исключить скрытый drift между editable source и bundle.
- Операбельность: одинаковый результат локально и в CI.
- Поддерживаемость: точечные правки по доменам вместо редактирования монолита.
- Контрактная безопасность: предотвратить непреднамеренные breaking changes.

## Decisions
- Decision 1: Однозначный source-of-truth
  - Editable source: `contracts/orchestrator/src/**`.
  - Delivery artifact: `contracts/orchestrator/openapi.yaml` (только generated).
  - Ручное редактирование `contracts/orchestrator/openapi.yaml` запрещается процессом и проверками.

- Decision 2: Единый bundle toolchain
  - Стандартизуем сборку на `Redocly CLI` (`split`/`bundle`) с закреплённой версией в scripts.
  - Причина выбора:
    - поддерживаемый инструмент для multi-file OpenAPI;
    - устойчивый `$ref` resolution для локальных файлов;
    - детерминированный bundle output при фиксированных входах.

- Decision 3: Обязательные команды `build` и `check`
  - Вводится отдельный script entrypoint для orchestrator-контракта (например, `build-orchestrator-openapi.sh`):
    - `build` собирает bundle;
    - `check` завершается ошибкой, если bundle устарел.
  - `check` используется как блокирующий gate в локальном workflow и CI.

- Decision 4: Bundle-first интеграция в существующие скрипты
  - `validate-specs.sh` сначала проверяет актуальность bundle, затем валидирует его.
  - `generate-all.sh` использует только готовый bundle как вход для codegen.
  - `check-breaking-changes.sh` сравнивает bundle-to-bundle (base/current).

- Decision 5: Явный, а не неявный Django export
  - `manage.py spectacular` остаётся отдельной явной операцией (`export-django-openapi.sh`).
  - Обычный generate pipeline не должен по умолчанию перезаписывать `contracts/orchestrator/openapi.yaml` из runtime export.

- Decision 6: Усиленные quality gates
  - Drift `src -> bundle` блокирует pipeline.
  - В CI отсутствующий `oasdiff` считается ошибкой (а не warning/fallback).
  - OpenAPI-валидация в CI должна опираться на полноценный validator (не только YAML parse).
  - Дополнительный parity gate на ключевые инварианты migration: `paths`, `operationId`, `components/schemas`.

## Alternatives considered
- Оставить монолит `contracts/orchestrator/openapi.yaml`:
  - Отклонено, т.к. не решает проблему сопровождения.

- Использовать `swagger-cli bundle` как стандартный bundler:
  - Отклонено как основной вариант, т.к. проект инструмента архивирован и несёт maintenance-риск.

- Делать только runtime export из Django (`manage.py spectacular`) и не вести модульные source-файлы:
  - Отклонено, т.к. это не решает задачу удобного contract-first редактирования и контроля drift.

- Не коммитить bundle в репозиторий:
  - Отклонено, т.к. ломает текущую совместимость tooling и локальный workflow.

## Audit Matrix (one-pass)
| Checkpoint | Status | Evidence | Impact | Remediation |
| --- | --- | --- | --- | --- |
| `contracts/orchestrator/src/**` отсутствует | Gap | В репозитории есть только `contracts/orchestrator/openapi.yaml` | Нет модульного source-of-truth | Ввести модульный layout и migration |
| Tooling завязан на единый bundle | OK | `validate-specs.sh`, `generate-all.sh`, `orval.config.ts` | Совместимость уже есть | Сохранить путь bundle неизменным |
| Drift-check отсутствует | Gap | Нет обязательного `check` режима | Высокий риск рассинхрона | Добавить `build/check` + блокирующий gate |
| Breaking-check деградирует без `oasdiff` | Risk | Fallback на простой `git diff` | Возможен пропуск breaking changes | В CI требовать `oasdiff` |
| Неявный runtime export может перезаписать bundle | Risk | `generate-all.sh` вызывает `export-django-openapi.sh` по mtime | Конфликт источников правды | Убрать неявный export из default workflow |
| Документация описывает монолитный workflow | Gap | QUICKSTART/CHECKLIST с редактированием `openapi.yaml` | Ошибки внедрения нового процесса | Обновить docs и troubleshooting |

## Migration Plan
1. Зафиксировать target layout `contracts/orchestrator/src/**` и naming conventions.
2. Добавить `build/check` bundle script (Redocly CLI), проверить детерминированность output.
3. Перенести текущий `openapi.yaml` в modular source без изменения API semantics.
4. Интегрировать `build/check` в `validate-specs.sh`, `generate-all.sh`, `check-breaking-changes.sh`.
5. Убрать неявный `manage.py spectacular` из стандартного generate workflow.
6. Добавить/обновить quality gates в pre-commit и CI.
7. Обновить docs и troubleshooting.
8. Прогнать verification suite (validate, generate, breaking-check, parity tests, openspec validate).

## Definition of Ready
- Подтверждён `Redocly CLI` как стандартный bundler.
- Подтверждён принцип: `src/**` editable, `openapi.yaml` generated-only.
- Согласованы блокирующие quality gates для local + CI.
- Назначены owners за contract scripts и документацию.

## Definition of Done
- Введён `contracts/orchestrator/src/**` и собранный `contracts/orchestrator/openapi.yaml`.
- Скрипты `validate/generate/check-breaking` работают в bundle-first режиме.
- Drift-check блокирует устаревший bundle.
- `oasdiff` обязателен в CI и используется для bundle-to-bundle comparison.
- Проверки parity и генерация артефактов проходят без регрессий.
- Документация полностью отражает новый workflow.

## Risks / Trade-offs
- Риск: усложнение pipeline дополнительным шагом сборки.
  - Mitigation: автоматизация `build/check` внутри текущих скриптов.
- Риск: ошибки миграции между монолитом и модулями.
  - Mitigation: parity checks по `paths`, `operationId`, `components/schemas`.
- Риск: расхождение между runtime export и contract source.
  - Mitigation: исключить неявный export из обычного workflow; оставить только explicit command.
- Риск: инструментальные зависимости в CI.
  - Mitigation: зафиксировать версии tooling и проверять их наличие ранним fail-fast шагом.

## Rollback Plan
- Если migration приводит к блокирующим проблемам:
  - временно вернуть bundle из последнего стабильного коммита;
  - отключить обязательность `src/**` только на время hotfix;
  - сохранить минимальный набор проверок validate + breaking-check;
  - после стабилизации повторить migration с теми же quality gates.

## Assumptions / Open Questions
- Assumption: Node/npm доступны в dev/CI для запуска `Redocly CLI`.
- Open questions: отсутствуют блокирующие вопросы для начала реализации.
