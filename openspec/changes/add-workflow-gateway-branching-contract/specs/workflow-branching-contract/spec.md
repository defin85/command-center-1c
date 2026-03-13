## ADDED Requirements
### Requirement: Workflow DAG MUST хранить first-class branch edge contract
Система ДОЛЖНА (SHALL) хранить branching semantics в persisted DAG edge как explicit typed contract, а не выводить их из canvas handle id, edge label или raw `edge.condition`.

Branch edge contract ДОЛЖЕН (SHALL) как минимум поддерживать:
- `branch.kind = "match" | "default"`;
- `branch.source_path` для `match`-ветвей;
- `branch.operator` из канонического supported set;
- `branch.expected_value`, когда этого требует оператор;
- operator-facing `branch.label` или эквивалентный stable caption.

Система НЕ ДОЛЖНА (SHALL NOT) считать `edge.condition` canonical analyst-facing branching contract на default surface.

#### Scenario: Gateway edge сохраняется как typed routing contract
- **GIVEN** аналитик соединяет gateway с downstream step
- **WHEN** он задаёт ветвь `route == "publish"`
- **THEN** DAG сохраняет explicit branch payload с `kind`, `source_path`, `operator` и `expected_value`
- **AND** routing не зависит от React Flow handle id или произвольного edge label

### Requirement: Exclusive Gateway MUST маршрутизировать ровно одну ветвь fail-closed
Система ДОЛЖНА (SHALL) поддерживать analyst-facing `gateway_exclusive`, который вычисляет outgoing `match`-ветви по branch edge contract и активирует:
- ровно одну `match`-ветвь; либо
- `default`-ветвь, если `match`-ветвей нет.

Система НЕ ДОЛЖНА (SHALL NOT) silently выбирать ветвь при множественных `match`-совпадениях. В таком случае runtime ДОЛЖЕН (SHALL) завершать выполнение fail-closed с structured routing diagnostic.

#### Scenario: Exclusive gateway выбирает одну ветвь по decision outcome
- **GIVEN** `Decision Task` записал `workflow.state.route = "publish"`
- **AND** у `gateway_exclusive` есть ветви `route == "publish"`, `route == "skip"` и `default`
- **WHEN** runtime оценивает gateway
- **THEN** активируется только ветвь `route == "publish"`
- **AND** остальные outgoing paths не становятся active для этого run

#### Scenario: Exclusive gateway падает при двух совпавших ветвях
- **GIVEN** у `gateway_exclusive` две `match`-ветви одновременно удовлетворяют текущему context
- **WHEN** runtime оценивает gateway
- **THEN** выполнение завершается fail-closed
- **AND** diagnostics содержат matched edges, source value и причину `ambiguous_exclusive_branch`

### Requirement: Inclusive Gateway MUST активировать все совпавшие ветви и поддерживать active-branch fan-in
Система ДОЛЖНА (SHALL) поддерживать analyst-facing `gateway_inclusive`, который активирует все outgoing `match`-ветви, удовлетворяющие branch edge contract.

Если ни одна `match`-ветвь не подходит, система ДОЛЖНА (SHALL) использовать `default`-ветвь при её наличии; иначе выполнение ДОЛЖНО (SHALL) завершаться fail-closed.

Runtime ДОЛЖЕН (SHALL) фиксировать `activated branch set` в lineage/state текущего run и использовать его при downstream fan-in, чтобы:
- ожидать только реально активированные upstream branches;
- игнорировать неактивные ветви текущего run;
- показывать auditable provenance выбранного маршрута.

#### Scenario: Inclusive gateway активирует две ветви и downstream merge ждёт только их
- **GIVEN** `gateway_inclusive` имеет три outgoing ветви `notify`, `publish`, `archive`
- **AND** текущий context активирует только `notify` и `publish`
- **WHEN** runtime продолжает выполнение workflow
- **THEN** обе ветви становятся active
- **AND** downstream node с fan-in не ждёт завершения `archive`, потому что эта ветвь не была активирована в данном run

### Requirement: Branch evaluation MUST быть typed, auditable и fail-closed
Система ДОЛЖНА (SHALL) поддерживать канонический набор branch operators для default analyst surface и оценивать их по typed value semantics, а не по неявной string truthiness.

Система ДОЛЖНА (SHALL):
- валидировать совместимость `branch.operator` и `branch.expected_value`;
- завершать выполнение fail-closed при missing `source_path`, invalid operator payload или неконсистентном branch contract;
- сохранять в run diagnostics evaluated `source_path`, `actual_value`, matched branches, default-branch usage и routing outcome.

#### Scenario: Invalid branch source path блокирует routing
- **GIVEN** gateway edge ссылается на `branch.source_path`, отсутствующий в runtime context
- **WHEN** runtime оценивает branching contract
- **THEN** выполнение завершается fail-closed
- **AND** diagnostics содержат `missing_branch_source_path`
- **AND** downstream steps не запускаются по неявному fallback
