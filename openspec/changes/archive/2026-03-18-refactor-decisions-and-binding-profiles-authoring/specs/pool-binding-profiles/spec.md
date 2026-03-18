## ADDED Requirements

### Requirement: Binding profile authoring MUST использовать structured selectors вместо ручного ввода opaque references на default path
Система ДОЛЖНА (SHALL) предоставлять на `/pools/binding-profiles` structured authoring path для выбора pinned workflow revision и decision revisions, используемых в reusable binding profile revision.

Default authoring form ДОЛЖНА (SHALL):
- выбирать workflow revision из searchable catalog/picker;
- выбирать decision revisions через slot-oriented editor;
- автоматически заполнять связанные workflow reference fields из выбранной revision;
- направлять пользователя к `/workflows` и `/decisions` как к canonical reference catalogs без необходимости ручного копирования ids.

Default authoring form НЕ ДОЛЖНА (SHALL NOT) требовать ручного ввода `workflow_definition_key`, `workflow_revision_id`, `workflow_revision`, `workflow_name` или raw `Decision refs JSON` как primary UX path.

Raw/manual payload editing МОЖЕТ (MAY) существовать только как explicit advanced mode для compatibility/debugging и НЕ ДОЛЖЕН (SHALL NOT) открываться как основной экран редактирования.

#### Scenario: Аналитик создаёт binding profile через workflow revision picker
- **GIVEN** аналитик открыл `/pools/binding-profiles`
- **WHEN** он создаёт новую reusable profile revision
- **THEN** workflow pin выбирается из searchable workflow revision catalog
- **AND** связанные workflow reference fields заполняются из выбранной revision без ручного copy-paste

#### Scenario: Slot-oriented decision editor заменяет raw JSON как primary path
- **GIVEN** аналитик настраивает decision refs для reusable profile revision
- **WHEN** он добавляет publication slots
- **THEN** UI позволяет выбрать decision revision из structured list `/decisions` и отдельно задать `slot_key`
- **AND** raw JSON не является primary способом ввода decision refs

#### Scenario: Advanced mode остаётся явным compatibility path
- **GIVEN** оператору требуется вручную проверить или поправить raw payload для debugging/compatibility
- **WHEN** он явно переключается в advanced mode
- **THEN** UI показывает raw/manual controls
- **AND** default authoring path остаётся structured и скрывает эти controls по умолчанию
