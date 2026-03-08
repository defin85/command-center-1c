## Context
Сейчас в системе уже есть все основные технические кирпичи:
- `templates` как каталог исполняемых операций;
- `workflow` как versioned DAG и execution runtime;
- `pool runs` как доменный фасад над публикацией;
- `document_policy.v1` и `document_plan_artifact.v1` как downstream runtime contracts.

Но analyst-facing модель расходится с исходной продуктовой идеей:
- `workflow` больше похож на low-level technical DAG, чем на библиотеку бизнес-схем;
- `pool` несёт слишком много ответственности: организации, topology, document rules, execution context;
- business rules смешаны с orchestration и runtime projection;
- system-managed runtime workflows протекают в тот же conceptual surface, что и user-authored workflows.

Пользовательская цель другая: аналитик должен авторить несколько переиспользуемых схем распределения через `workflow`, а конкретные `pool`-ы должны выбирать и запускать эти схемы.

## Goals
- Сохранить текущий стек и runtime, не вводя внешний BPMN/DMN engine.
- Сделать `workflow` analyst-facing схемой распределения/публикации.
- Вынести business rules в явный decision layer вместо неструктурированного набора `condition`/inline logic.
- Позволить одному `pool` использовать несколько workflow-схем одновременно через versioned bindings.
- Оставить `templates` атомарными операциями.
- Сохранить `pool runs` как primary domain instance surface для операторов.
- Сохранить deterministic/fail-closed compile path до concrete runtime artifacts.

## Non-Goals
- Не строить полную стандартную BPMN/DMN-совместимость с XML как обязательный контракт первого релиза.
- Не делать generic low-code platform для любых процессов за пределами pool distribution/publication.
- Не поддерживать две равноправные analyst-facing модели (`workflow-centric` и `pool-edge document authoring`) на постоянной основе.
- Не трогать transport-owner execution architecture и worker backends сверх необходимого compile/runtime plumbing.

## Decisions
### Decision 1: Использовать BPMN/DMN принципы без внешнего engine
Система принимает принципы:
- orchestration отдельно от rules;
- process definition отдельно от process instance;
- reusable subprocess отдельно от копирования graph;
- version binding отдельно от “latest by accident”.

Но реализация остаётся на текущем стеке (`React Flow` UI, Django/Go/Python runtime, existing workflow engine).

### Decision 2: Workflow definition становится analyst-facing схемой
`workflow definition` становится главным артефактом, которым аналитик описывает:
- стадии процесса;
- доменные task types;
- approval/gates;
- subprocess reuse;
- decision points;
- role-aware orchestration.

Это не просто technical DAG storage, а primary scheme library для pools.

### Decision 3: Вводится явный decision layer (DMN-lite)
Вместо неструктурированного роста `condition`-логики вводится versioned decision resource:
- `decision_table` / `rule_table`;
- pinned revision;
- explicit input/output contract;
- deterministic evaluation.

Workflow вызывает decision как first-class node/reference, а не хранит основные бизнес-правила в произвольных строковых условиях.

На первом этапе decision layer не обязан быть полноценным DMN XML; достаточно компактного versioned contract на текущем стеке.

### Decision 4: Templates остаются атомарными операциями
`/templates` остаётся catalog of atomic execution building blocks.

Шаблоны отвечают на вопрос “чем выполнить шаг”, а не “какая схема применяется к обществу”.

Если `workflow` executor kind сохраняется, он рассматривается как compatibility path, а не как primary composition model для analyst-facing схем.

### Decision 5: Pool становится организационным контуром и binding target
`pool` продолжает описывать:
- состав/топологию организаций;
- master data context;
- tenant-specific structural constraints.

Но `pool` перестаёт быть primary местом, где аналитик руками авторит document semantics для новых схем.

Для этого вводится `pool_workflow_binding`, который связывает:
- `pool`;
- pinned `workflow revision`;
- pinned decision refs/parameters;
- role mapping;
- effective period;
- launch selectors/metadata.

### Decision 6: Pool run остаётся primary domain process instance surface
`/pools/runs` остаётся основным UX для операторов:
- create run;
- inspect;
- safe commands;
- retry;
- diagnostics.

`workflow_execution` остаётся engine/runtime object для наблюдаемости и дебага, но не заменяет доменный фасад `pool run`.

### Decision 7: Workflow/decision authoring компилируется в concrete runtime projection
Analyst-facing workflow/decision model не исполняется “как есть” на publication backend.

Перед запуском или на этапе activation/build система компилирует binding в concrete runtime projection:
- executable workflow graph;
- concrete `document_policy.v1`;
- downstream `document_plan_artifact.v1`;
- provenance и pinned references.

Это сохраняет deterministic retry/replay и не ломает текущие runtime contracts.

### Decision 8: Authored и system-managed workflows разделяются
Система должна различать:
- user-authored workflow definitions;
- system-managed/generated runtime workflow projections.

Generated runtime workflows не должны отображаться в analyst-facing `/workflows` как обычные редактируемые definitions.

### Decision 9: Big-bang authoring cutover
Для analyst-facing authoring система выбирает один primary путь:
- новые схемы создаются как workflow definitions с decision layer;
- новые pool binding-и используют именно workflow-centric model;
- direct edge-level `document_policy` authoring больше не развивается как основной путь для новых сценариев.

Historical runs и compatibility read-model допускаются, но новая функциональность не должна размываться между двумя source-of-truth моделями.

### Decision 10: Этот change supersedes separate business-scheme direction
Вместо отдельной analyst-facing сущности `business_scheme` система использует `workflow definition` как библиотеку схем.

Отдельный артефакт `business_scheme` не вводится, если тот же reuse и versioning можно получить на существующем workflow surface с decision layer.

## Trade-offs
- Плюс: остаёмся на текущем стеке и используем уже существующий workflow engine/UI.
- Плюс: analyst reuse появляется без размножения `pool`.
- Плюс: `templates` и `pool runs` сохраняют понятные границы ответственности.
- Минус: workflow model придётся существенно обогатить и “одомашнить” для аналитика.
- Минус: это big-bang смена primary authoring model, а не косметическая эволюция.
- Минус: придётся жёстко управлять boundary между analyst model и generated runtime model.

## Migration / Cutover Plan
1. Определить канонические модели `workflow definition`, `decision`, `pool_workflow_binding`.
2. Добавить analyst-friendly workflow/decision notation и validation rules.
3. Добавить compile path `binding -> runtime workflow projection + document_policy.v1`.
4. Перевести `/pools/runs` create path на binding-based launch.
5. Разделить authored `/workflows` и generated runtime workflow views.
6. Заморозить legacy edge-level `document_policy` authoring как primary путь для новых сценариев.
7. Сохранить historical run readability и debug lineage на переходный период.

## Open Questions
- Decision layer должен быть отдельным top-level ресурсом (`/decisions`) или versioned частью workflow package/deployment bundle?
- Какая часть существующего `pool` topology остаётся analyst-editable после cutover, а какая становится purely structural/runtime concern?
