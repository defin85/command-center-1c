## ADDED Requirements

### Requirement: Decision authoring surfaces MUST использовать structured reference catalogs как default path
Система ДОЛЖНА (SHALL) предоставлять для analyst-facing decision authoring общий structured reference catalog для workflow revisions и decision revisions, переиспользуемый между `/decisions`, `/workflows` и связанными authoring surfaces.

Default authoring path НЕ ДОЛЖЕН (SHALL NOT) требовать от пользователя ручного copy-paste opaque ids между страницами как primary UX.

Raw/manual reference entry МОЖЕТ (MAY) существовать только как explicit advanced или compatibility path и НЕ ДОЛЖЕН (SHALL NOT) быть единственным или основным способом выбора reusable references.

Pinned inactive или вне default selection revisions ДОЛЖНЫ (SHALL) оставаться читаемыми и различимыми в selectors/detail surfaces, чтобы пользователь не терял lineage context при revise/rollover сценариях.

#### Scenario: Аналитик выбирает reusable references без копирования opaque ids
- **GIVEN** аналитик работает с versioned workflow и decision resources
- **WHEN** он открывает `/decisions` или связанную authoring surface
- **THEN** UI предлагает structured selectors/search surface для выбора revisions
- **AND** пользователю не требуется вручную переносить `decision_table_id`, `decision_revision` или другие opaque ids между страницами как primary path

#### Scenario: Inactive revision остаётся видимой вне default candidate set
- **GIVEN** ранее pinned decision revision больше не входит в default active selection
- **WHEN** аналитик открывает revise или rollover flow
- **THEN** UI продолжает показывать эту revision как текущий lineage context
- **AND** отличает её от default ready-to-pin candidates
