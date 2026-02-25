## ADDED Requirements
### Requirement: Pool runtime distribution steps MUST использовать алгоритмический source-of-truth
Система ДОЛЖНА (SHALL) исполнять шаги `pool.distribution_calculation.top_down` и `pool.distribution_calculation.bottom_up` через канонические алгоритмы распределения/агрегации, а не через summary-only вычисления.

Система ДОЛЖНА (SHALL) сохранять результат этих шагов как детерминированный runtime artifact, который используется шагами `reconciliation_report` и `publication_odata`.

#### Scenario: Workflow runtime использует active topology version в distribution step
- **GIVEN** для пула существуют versioned узлы и рёбра
- **AND** run выполняется за конкретный период
- **WHEN** workflow runtime исполняет `distribution_calculation`
- **THEN** расчёт использует только topology-версию, активную на этот период
- **AND** результат сохраняется в execution context как структурированный artifact

### Requirement: Reconciliation MUST блокировать publication при нарушении distribution invariants
Система ДОЛЖНА (SHALL) завершать execution fail-closed до старта `pool.publication_odata`, если нарушены инварианты распределения:
- несходимость баланса;
- gaps покрытия активной цепочки publish-target узлов;
- отсутствие или неконсистентность required distribution artifact.

Система ДОЛЖНА (SHALL) возвращать machine-readable fail-closed код, который сохраняется в execution diagnostics и проецируется во внешний pools facade.

#### Scenario: Нарушение сходимости блокирует publication step
- **GIVEN** distribution/reconciliation обнаружили несходимость исходной суммы
- **WHEN** runtime оценивает переход к `pool.publication_odata`
- **THEN** публикационный шаг не запускается
- **AND** execution завершается fail-closed с machine-readable кодом
- **AND** facade diagnostics возвращает тот же код без деградации

#### Scenario: Coverage gap в активной цепочке блокирует publication step
- **GIVEN** distribution artifact не покрывает активный publish-target узел цепочки
- **WHEN** runtime выполняет reconciliation gate
- **THEN** run останавливается до publication
- **AND** оператор получает machine-readable diagnostics с причиной gap coverage

### Requirement: Distribution artifact MUST быть стабильным upstream контрактом для downstream compile слоёв
Система ДОЛЖНА (SHALL) формировать versioned `distribution_artifact`, пригодный для потребления downstream compile слоями (`document_plan_artifact`, atomic workflow graph compile) без повторного чтения/доверия к raw `run_input`.

Система НЕ ДОЛЖНА (SHALL NOT) допускать обход этого контракта в create-run path через произвольный raw payload.

Минимальный обязательный набор полей `distribution_artifact.v1`:
- `version`;
- `topology_version_ref`;
- `node_totals[]`;
- `edge_allocations[]`;
- `coverage`;
- `balance`;
- `input_provenance`.

#### Scenario: Downstream compile использует только distribution artifact как вход распределения
- **GIVEN** create-run distribution завершён и сохранён versioned `distribution_artifact`
- **WHEN** runtime переходит к downstream compile (document plan или atomic graph)
- **THEN** вход распределения берётся из `distribution_artifact`
- **AND** raw `run_input` не используется как authoritative источник распределённых сумм

#### Scenario: Runtime отклоняет неполный distribution artifact контракт
- **GIVEN** execution context содержит artifact без одного из обязательных полей `distribution_artifact.v1`
- **WHEN** runtime пытается выполнить downstream compile/reconciliation
- **THEN** run завершается fail-closed до publication
- **AND** diagnostics содержит machine-readable код нарушения artifact-контракта
