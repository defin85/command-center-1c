## ADDED Requirements
### Requirement: Pool run distribution MUST гарантировать полное покрытие активной цепочки организаций
Система ДОЛЖНА (SHALL) рассчитывать распределение для create-run path на основе активной версии DAG topology (`effective_from/effective_to`) за период run.

Система ДОЛЖНА (SHALL) обеспечивать, что распределение покрывает активную цепочку организаций, участвующую в публикации, и не оставляет нераспределённый денежный остаток вне допуска денежной точности.

#### Scenario: Top-down распределение полностью покрывает многоуровневую цепочку
- **GIVEN** активный граф пула содержит многоуровневую цепочку `root -> level1 -> level2`
- **AND** run запущен в `top_down` со стартовой суммой
- **WHEN** выполняется шаг `distribution_calculation.top_down`
- **THEN** суммы распределяются по рёбрам с учётом `weight/min_amount/max_amount`
- **AND** итоговая сумма по целевым узлам совпадает с исходной суммой в пределах денежной точности
- **AND** в runtime artifact нет gaps покрытия для активных publish-target узлов

#### Scenario: Bottom-up распределение сходится к root без потери входной суммы
- **GIVEN** run запущен в `bottom_up` и содержит валидный source payload
- **WHEN** выполняется шаг `distribution_calculation.bottom_up`
- **THEN** суммы агрегируются по активной topology до root
- **AND** `root_total` совпадает с суммой принятых входных строк в пределах денежной точности
- **AND** при несходимости run маркируется fail-closed до шага публикации

### Requirement: Create-run publication payload MUST строиться из distribution artifacts
Система ДОЛЖНА (SHALL) формировать `pool_runtime_publication_payload.documents_by_database` для create-run path из канонического runtime distribution artifact.

Система НЕ ДОЛЖНА (SHALL NOT) использовать raw `run_input` как authoritative источник итогового publication payload, если рассчитанный distribution artifact уже сформирован.

#### Scenario: Runtime игнорирует raw publication payload при наличии расчётного artifact
- **GIVEN** create-run запрос содержит `run_input` с полем `documents_by_database`
- **AND** шаги распределения успешно сформировали канонический distribution artifact
- **WHEN** runtime формирует payload для `pool.publication_odata`
- **THEN** используется payload из distribution artifact
- **AND** raw `run_input.documents_by_database` не может обойти инварианты покрытия и сходимости
