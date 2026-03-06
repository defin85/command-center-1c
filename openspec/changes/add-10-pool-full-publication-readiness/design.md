## Context
На текущем dev-контуре pool run может завершаться workflow-статусом, но оператор не получает достоверную картину "прошло ли распределение end-to-end корректно":
- документы часто публикуются с минимальным payload;
- master-data hub и bindings не подготовлены как обязательный upstream;
- read-model попыток публикации не всегда отражает реальные atomic публикации;
- UI acceptance сценарий опирается на моки и не доказывает боевую трассу.

Нужен единый процесс, где один и тот же run проходит:
1) readiness checks,
2) реальное исполнение через UI,
3) post-run OData verification,
4) прозрачный run report с блокерами и итогом.

## Goals / Non-Goals
### Goals
- Ввести детерминированный режим `minimal_documents_full_payload` для top-down run.
- Сделать readiness блокеры явными и machine-readable до публикации.
- Обеспечить прозрачную проекцию publication attempts для всех atomic публикаций.
- Добавить OData verifier по опубликованным refs с проверкой полноты payload.
- Зафиксировать live UI acceptance path для dev без API-моков.

### Non-Goals
- Не менять бизнес-алгоритм распределения сумм top-down/bottom-up.
- Не вводить новый источник master-data вне существующего hub.
- Не заменять существующие API Pools на новый протокол.

## Decisions
### Decision 1: Test-first и единый acceptance pipeline
Сначала добавляются red-тесты:
- backend integration для run lifecycle + publication/read-model;
- OData verifier tests для completeness checks;
- UI live e2e для операторского пути.
Только затем включаются изменения в runtime/policy/projection до green.

### Decision 2: Явный профиль полноты документа
Добавляется декларативный профиль `minimal_documents_full_payload`:
- минимизация числа документов разрешена;
- для каждого `entity_name` задаются обязательные реквизиты и табличные части;
- отсутствие обязательного элемента блокирует публикацию fail-closed.

### Decision 3: Readiness как отдельный доменный слой перед publication
До `pool.publication_odata` вычисляется `readiness_blockers`:
- отсутствующие canonical master-data;
- отсутствующие Organization->Party bindings;
- неполный policy mapping.
Если блокеры есть, run не переходит к OData side effects.

### Decision 4: Projection attempts агрегируется из всех atomic publication nodes
Проекция больше не зависит от единственного первого найденного publication payload.
Она агрегирует все `publication_odata` узлы текущего execution и формирует консистентный read-model для UI report.

### Decision 5: OData verify как независимая пост-проверка по refs
Verifier получает refs из execution результата и сверяет объекты в OData:
- auth только через UTF-8 Basic header;
- сверка header/table part полей по completeness profile;
- детерминированный mismatch report.

### Decision 6: Прозрачный операторский путь в UI
UI показывает:
- readiness checklist до запуска;
- статус run step-by-step;
- verification summary после завершения.
Это устраняет "чёрный ящик" между запуском и фактическим состоянием документов.

### Decision 7: Первый full-run baseline ограничивается одним стабильным BP 3.0 сценарием
Для первого полного dev acceptance baseline выбирается один реальный OData-паттерн вместо попытки покрыть все варианты типовых документов сразу:
- infobase: `stroygrupp_7751284461`;
- entity: `Document_РеализацияТоваровУслуг`;
- variant: `ВидОперации = Услуги`;
- required table part: `Услуги`.

Подробные результаты исследования сохранены в `artifacts/odata-document-baseline-2026-03-06.md`.

## Trade-offs
- Увеличивается число проверок до публикации, но это снижает риск пустых документов и скрытых ошибок.
- Агрегированная проекция attempts сложнее текущей, но даёт наблюдаемость и корректный отчёт.
- Live e2e медленнее моков, но именно он подтверждает реальную интеграцию.

## Risks / Mitigations
- Риск: неполный completeness profile для отдельных entity.
  - Mitigation: fail-closed validation + явный checklist per entity.
- Риск: один `entity_name` может иметь несколько валидных форм заполнения между базами и даже внутри одной базы.
  - Mitigation: первый rollout ограничивается одним baseline; variant-aware policy вводится отдельным следующим шагом.
- Риск: текущий DSL не умеет выражать derived fields BP 3.0 (`СуммаНДС`, потенциально quantity*price и т.п.).
  - Mitigation: первый dev acceptance фиксируется как deterministic fixed-amount baseline; arithmetic/value-derivation выносится отдельным следующим шагом.
- Риск: canonical master-data surface пока уже, чем реальные BP payload dependencies (currency/accounts/subconto/employees).
  - Mitigation: для baseline допускаются literals/IB refs; для production rollout нужен отдельный этап расширения tokenized master-data model.
- Риск: historical run-ы могут иметь legacy структуру payload.
  - Mitigation: staged rollout и backward-compatible projection parsing.
- Риск: OData verify может быть нестабильным по auth/transport.
  - Mitigation: единый UTF-8 Basic path и retry/backoff в verifier.

## Migration Plan
1. Зафиксировать spec и acceptance checklist.
2. Добавить red tests (backend + verifier + UI live).
3. Внедрить readiness blockers и policy completeness validation.
4. Внедрить aggregation projection attempts.
5. Внедрить OData verifier в run acceptance path.
6. Включить в dev, собрать отчёты, затем расширять rollout.

## Open Questions
- Полный перечень обязательных полей/табличных частей по каждому `entity_name` должен быть зафиксирован отдельной матрицей (`Requirement -> entity -> field/table`).
- Для production-like expansion нужен variant-aware completeness profile (`entity_name + operation variant`), так как живые BP 3.0 базы показывают разные валидные формы одного и того же документа.
- Нужно ли хранить результаты OData verify как отдельный immutable artifact или достаточно run report read-model.
- Нужен ли arithmetic/value-derivation слой в `document_policy`, либо допускается ограниченный список server-computed BP fields как explicit exception для readiness/completeness.
