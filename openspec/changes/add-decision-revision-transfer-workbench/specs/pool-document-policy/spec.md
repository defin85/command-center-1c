## ADDED Requirements
### Requirement: Document policy transfer MUST produce explicit remap diagnostics against target metadata snapshot
Система ДОЛЖНА (SHALL) при переносе `document_policy` из source revision в target metadata context строить явный remap/transfer report относительно resolved target metadata snapshot выбранной ИБ.

Transfer/remap contract ДОЛЖЕН (SHALL):
- классифицировать элементы source policy как `matched`, `ambiguous`, `missing` или `incompatible`;
- считать `matched` элементы готовыми к переносу без дополнительного remap;
- требовать явного analyst confirmation/remap для `ambiguous`, `missing` и `incompatible` элементов;
- валидировать итоговый policy против target metadata snapshot до publish новой revision;
- сохранять target metadata provenance в resulting revision вместо provenance source revision.

Система НЕ ДОЛЖНА (SHALL NOT) публиковать новую revision молча, если remap/transfer report содержит unresolved `ambiguous`, `missing` или `incompatible` элементы.

#### Scenario: Полностью matched перенос использует source revision как template и target snapshot как contract
- **GIVEN** source `document_policy` переносится в target database, где все metadata references однозначно совпали с target snapshot
- **WHEN** аналитик запускает transfer flow
- **THEN** transfer report помечает все элементы как `matched`
- **AND** publish новой revision всё равно сохраняет target metadata provenance, а не provenance source revision

#### Scenario: Ambiguous или missing remap блокирует publish fail-closed
- **GIVEN** transfer report содержит `ambiguous` или `missing` metadata references
- **WHEN** аналитик пытается опубликовать новую revision без явного remap этих элементов
- **THEN** publish отклоняется fail-closed
- **AND** source revision и existing pinned consumers остаются неизменными

#### Scenario: Resulting revision сохраняет target provenance после переноса между profile versions
- **GIVEN** source revision была опубликована под другой `configuration profile` или другой версией target profile
- **WHEN** аналитик завершает transfer и публикует новую revision
- **THEN** resulting revision сохраняет provenance target `configuration profile` и target `metadata snapshot`
- **AND** downstream compatibility checks опираются на target context новой revision, а не на context source revision
