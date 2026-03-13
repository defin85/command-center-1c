## Context
Сейчас analyst-facing workflow surface смешивает две разные ответственности:
- decision evaluation через pinned `decision_ref`;
- branching/orchestration через `condition`-node, который фактически приводит результат к `bool`.

При этом default authoring boundary уже запрещает raw `edge.condition`, а canvas всё ещё рисует `true/false/default` handles, которые не закреплены explicit persisted contract. Это создаёт разрыв между UX и реальной runtime semantics.

## Goals / Non-Goals

### Goals
- Разделить вычисление decision outputs и маршрутизацию ветвей.
- Ввести analyst-facing `Decision Task`, `Exclusive Gateway`, `Inclusive Gateway`.
- Ввести typed persisted `branch edge contract`.
- Убрать зависимость branch semantics от raw `edge.condition`, edge label и canvas handle id.
- Зафиксировать fail-closed runtime semantics, auditable diagnostics и activated-branch provenance.
- Сохранить compatibility execution для legacy workflow, не ломая уже сохранённые DAG.

### Non-Goals
- Не вводить полный BPMN/DMN-движок и не копировать весь BPMN vocabulary.
- Не заменять decision tables другой rule-engine моделью.
- Не переписывать все historical workflow автоматически в момент миграции.
- Не делать `/decisions` workflow branching surface; decision lifecycle остаётся отдельным reference catalog.

## Decisions

### Decision 1: Не расширять текущий `condition`-node до универсального branching-конструкта
`condition`-node уже несёт compatibility baggage:
- compiled boolean expression;
- implicit bool coercion;
- legacy raw-expression mode;
- misleading split-handles без persisted semantics.

Поэтому analyst-facing branching model должен перейти на новые узлы:
- `decision` — вычисляет pinned decision revision и пишет outputs в context;
- `gateway_exclusive` — выбирает ровно одну ветвь или `default`;
- `gateway_inclusive` — активирует одну или несколько ветвей, а downstream readiness опирается только на active branches текущего run.

Legacy `condition` остаётся compatibility-only.

### Decision 2: Branch semantics должны храниться в edge contract, а не выводиться из UI
Выбран explicit `branch edge contract`, который живёт в persisted DAG edge.

Базовая модель:
- `branch.kind = "match" | "default"`
- `branch.source_path` — путь к значению в runtime context (`result.*`, `decisions.*`, `workflow.state.*`, и т.д.)
- `branch.operator` — минимальный typed набор для v1: `equals`, `not_equals`, `in`, `truthy`, `falsy`
- `branch.expected_value` — JSON scalar или scalar array, когда это требуется оператором
- `branch.label` — operator-facing caption для designer/read-model

Это позволяет:
- валидировать DAG без зависимости от canvas;
- сериализовать/десериализовать branch semantics детерминированно;
- строить future-proof diagnostics и lineage.

### Decision 3: `Decision Task` не ветвит сам, а публикует typed outputs
`Decision Task` должен:
- всегда ссылаться на pinned `decision_ref`;
- использовать explicit input/output mapping;
- публиковать result payload в context;
- не иметь собственных branching rules.

Gateway читает outputs decision-task через `branch.source_path`.

Это сохраняет правильное разделение:
- decision layer определяет business outcome;
- gateway layer определяет orchestration route.

### Decision 4: Inclusive branching требует activated-branch provenance
Для `gateway_inclusive` недостаточно просто выбрать несколько outgoing edges. Runtime должен фиксировать, какие ветви были реально активированы в данном run, чтобы downstream fan-in:
- ждал только active predecessors;
- не блокировался на неактивных branch edges;
- мог объяснить route provenance в run diagnostics.

Это не требует полного BPMN token engine, но требует явного active-branch tracking в runtime state/lineage.

### Decision 5: Ambiguous и missing routing должны быть fail-closed
Branching semantics не должны зависеть от неявного порядка edge-ов.

Правила:
- `gateway_exclusive`: ровно одно `match`-branch, либо `default`; при множественных match — fail-closed.
- `gateway_inclusive`: одна или несколько `match`-ветвей, либо `default`, если match нет; при некорректном contract или неразрешимом source-path — fail-closed.
- Raw `edge.condition` и свободные inline expressions не являются canonical branching model.

## Alternatives considered

### Alternative A: Оставить `Decision Gate`, но разрешить больше edge conditions
Отклонено:
- смешивает decision evaluation и orchestration;
- возвращает analyst surface к raw expressions;
- не решает проблему persisted branch semantics.

### Alternative B: Кодировать branch semantics через canvas handle ids
Отклонено:
- handle ids являются UI-деталью, а не domain contract;
- backend/runtime не должны зависеть от React Flow internals;
- невозможно нормально валидировать/мигрировать DAG вне UI.

### Alternative C: Сразу внедрить полный BPMN gateway/token engine
Отложено:
- слишком широкий объём для текущей задачи;
- проекту нужен канонический analyst-facing branch contract, а не полный BPMN vocabulary.

## Risks / Trade-offs
- Появится новый DAG vocabulary и миграционный слой для legacy workflow.
- Inclusive fan-in потребует доп. runtime bookkeeping.
- Понадобится обновление frontend adapters, generated models и authoring UX одновременно, иначе designer и runtime разойдутся.
- Придётся аккуратно переименовать/переосмыслить текущий `Decision Gate`, чтобы не сломать mental model пользователей.

## Migration Plan
1. Добавить новые node types и branch edge contract в schema/API/runtime.
2. Оставить legacy `condition` и raw `edge.condition` исполнимыми, но перевести их в compatibility-only/read-only authoring path.
3. Добавить guided migration в UI:
   - legacy condition -> `Decision Task + Gateway`;
   - raw edge condition -> typed branch edge rule.
4. Обновить docs и diagnostics так, чтобы новые workflow создавались только через canonical branching model.

## Open Questions
- Нужен ли v1-operator `matches_any` сверх `in`, если decision возвращает массив/список?
- Нужно ли в v1 явно показывать branch priority в designer, если `gateway_exclusive` и так fail-closed при нескольких match?
