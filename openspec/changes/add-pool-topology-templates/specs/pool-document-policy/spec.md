## ADDED Requirements

### Requirement: Template-instantiated topology MUST materialize explicit document policy selectors
Если topology создаётся или обновляется через `topology_template_revision`, система ДОЛЖНА (SHALL) materialize'ить template edge defaults в explicit concrete `edge.metadata.document_policy_key`.

`edge.metadata.document_policy_key` ДОЛЖЕН (SHALL) оставаться canonical selector для downstream binding/runtime resolution и после template-based authoring.

#### Scenario: Template edge default превращается в canonical concrete selector
- **GIVEN** template edge содержит default `document_policy_key=receipt`
- **WHEN** pool instantiation materialize'ит concrete topology
- **THEN** resulting concrete edge содержит `edge.metadata.document_policy_key=receipt`
- **AND** document plan/runtime compile используют его как обычный explicit topology selector

### Requirement: Document policy resolution MUST оставаться fail-closed без graph-position fallback
При template-based topology authoring система НЕ ДОЛЖНА (SHALL NOT) silently выводить `document_policy_key` только из положения edge или узла в графе, если explicit selector отсутствует после materialization.

Отсутствие explicit selector ДОЛЖНО (SHALL) приводить к existing missing-slot или missing-selector diagnostics, а не к автоматическому выбору `multi`, `receipt`, `realization` или другой policy slot.

#### Scenario: Leaf edge без explicit selector не получает auto-generated receipt
- **GIVEN** template-based topology содержит edge до leaf узла
- **AND** после materialization у concrete edge отсутствует `document_policy_key`
- **WHEN** preview или create-run path пытается собрать document plan
- **THEN** система не назначает `receipt` автоматически только потому, что edge ведёт в leaf
- **AND** shipped path завершается fail-closed с явной диагностикой отсутствующего selector
