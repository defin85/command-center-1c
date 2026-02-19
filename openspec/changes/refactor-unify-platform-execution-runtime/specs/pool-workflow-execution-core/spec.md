## ADDED Requirements
### Requirement: Pool workflow compiler MUST детализировать run до атомарных execution шагов
Система ДОЛЖНА (SHALL) компилировать `pool run` в атомарный workflow graph, где шаги отражают конкретные доменные действия по рёбрам/документам, а не только coarse-grained этапы.

Атомарный graph ДОЛЖЕН (SHALL) строиться из:
- distribution artifact (coverage + allocations);
- document plan artifact (document chains, field/table mappings, invoice rules).

Система ДОЛЖНА (SHALL) генерировать deterministic `node_id` для атомарных шагов на основе стабильных бизнес-ключей (`edge_id`, `document_role`, `action_kind`, `attempt_scope`).

#### Scenario: Pool run компилируется в per-edge/per-document workflow nodes
- **GIVEN** активная topology содержит несколько рёбер и document chain policy
- **WHEN** runtime компилирует execution plan для run
- **THEN** DAG содержит атомарные nodes по рёбрам и документам
- **AND** каждый node имеет стабильный deterministic `node_id`

### Requirement: Invoice-required policy MUST материализоваться отдельными атомарными шагами
Система ДОЛЖНА (SHALL) для policy с `invoice_mode=required` компилировать отдельные invoice nodes и link dependencies в execution graph.

Система НЕ ДОЛЖНА (SHALL NOT) считать публикацию завершённой, если обязательный invoice node отсутствует или завершился неуспешно.

#### Scenario: Required invoice формирует отдельный шаг и влияет на terminal projection
- **GIVEN** document chain требует связанную счёт-фактуру (`invoice_mode=required`)
- **WHEN** run выполняется через workflow runtime
- **THEN** invoice публикуется отдельным atomic node
- **AND** при его fail статус run не может перейти в `published`

### Requirement: Retry MUST работать по failed atomic nodes
Система ДОЛЖНА (SHALL) строить retry execution для `pool run` по подмножеству failed atomic nodes с учетом зависимостей, без повторного исполнения уже успешных атомарных шагов.

#### Scenario: Partial failure вызывает retry только проблемных атомарных шагов
- **GIVEN** run завершился с failed atomic nodes при части уже успешных шагов
- **WHEN** оператор инициирует retry
- **THEN** runtime формирует retry graph только для failed subset и необходимых зависимостей
- **AND** успешные шаги не исполняются повторно
