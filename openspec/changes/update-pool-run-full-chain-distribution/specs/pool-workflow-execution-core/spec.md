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
