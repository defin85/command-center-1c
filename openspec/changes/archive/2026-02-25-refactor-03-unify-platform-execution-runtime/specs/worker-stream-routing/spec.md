## ADDED Requirements
### Requirement: Worker stream routing MUST сохранять unified runtime parity между lanes
Система ДОЛЖНА (SHALL) при маршрутизации по разным stream names сохранять единый execution envelope и единые semantics событий (`queued`, `processing`, `completed`, `failed`) для всех lane-ов.

Система ДОЛЖНА (SHALL) обеспечивать, что lane (`operations`/`workflows`) отражается в telemetry/metadata, но не меняет lifecycle contract исполнения.

#### Scenario: Workflow lane и operations lane публикуют совместимые события
- **GIVEN** один worker deployment читает `commands:worker:operations`
- **AND** другой worker deployment читает `commands:worker:workflows`
- **WHEN** оба deployment публикуют status events
- **THEN** event payload и lifecycle semantics совместимы с единым runtime-контрактом
- **AND** observability слой может агрегировать события без lane-specific ветвления бизнес-логики
