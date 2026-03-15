## ADDED Requirements

### Requirement: Pool workflow binding decisions MUST выступать именованными publication slots
Система ДОЛЖНА (SHALL) трактовать `pool_workflow_binding.decisions[].decision_key` как canonical slot name для policy-bearing decisions внутри binding.

Binding МОЖЕТ (MAY) pin-ить несколько publication slot decisions одновременно.

`decision_key` ДОЛЖЕН (SHALL) быть уникальным в пределах одного binding.

Topology edge selector `edge.metadata.document_policy_key` ДОЛЖЕН (SHALL) резолвиться только против decisions, pinned в выбранном binding.

#### Scenario: Один binding pin-ит несколько publication slots
- **GIVEN** binding содержит decisions с `decision_key=sale` и `decision_key=purchase`
- **WHEN** оператор открывает binding preview
- **THEN** preview показывает оба slot'а как часть effective projection
- **AND** runtime может использовать их независимо на разных topology edges

#### Scenario: Duplicate decision_key отклоняется fail-closed
- **GIVEN** оператор или backend пытается сохранить binding, где два decision refs имеют одинаковый `decision_key`
- **WHEN** выполняется validation binding contract
- **THEN** запрос отклоняется fail-closed
- **AND** canonical binding store не сохраняет ambiguous slot mapping

### Requirement: Binding workspace UI MUST быть analyst-friendly slot-oriented surface
Система ДОЛЖНА (SHALL) предоставлять binding workspace как analyst-friendly surface для управления named publication slots, а не как low-level editor raw decision refs.

Binding UI ДОЛЖЕН (SHALL):
- показывать `decision_key` как primary slot identity;
- показывать pinned decision revision для каждого slot;
- показывать coverage slot'а относительно topology edge selectors выбранного пула;
- явно показывать missing или ambiguous slot coverage до preview/create-run.

Raw identifiers (`decision_table_id`, внутренние ids) МОГУТ (MAY) оставаться в advanced/read-only diagnostics, но НЕ ДОЛЖНЫ (SHALL NOT) быть primary editing model.

#### Scenario: Аналитик видит binding как набор named slots, а не raw ids
- **GIVEN** оператор или аналитик открыл binding workspace
- **WHEN** UI рендерит decisions section
- **THEN** основная модель экрана показывает named slots и pinned revisions
- **AND** ручной ввод raw decision ids не является основным способом редактирования

#### Scenario: Binding workspace показывает непокрытые topology selectors до preview
- **GIVEN** активная topology содержит edge с `document_policy_key=return`
- **AND** binding не содержит matching slot `return`
- **WHEN** аналитик открывает binding workspace
- **THEN** UI показывает missing coverage до запуска preview
- **AND** normal save/run path блокируется или помечается blocking remediation diagnostic

#### Scenario: Binding workspace показывает ambiguous coverage context отдельно от missing slot
- **GIVEN** topology coverage зависит от binding context, который не выбран детерминированно
- **WHEN** аналитик открывает binding workspace
- **THEN** UI показывает ambiguous coverage context как отдельное состояние
- **AND** не смешивает его с missing `decision_key` внутри выбранного binding

## MODIFIED Requirements

### Requirement: Pool workflow binding MUST предоставлять preview effective runtime projection
Система ДОЛЖНА (SHALL) предоставлять preview binding-а до запуска, достаточный для понимания:
- какой workflow revision будет выполнен;
- какие decisions/parameters будут применены;
- какие named publication slots доступны для topology resolution;
- какие topology selectors остаются непокрытыми или ambiguous;
- какая concrete runtime projection будет собрана;
- какой lineage получит run.

Binding preview ДОЛЖЕН (SHALL) показывать coverage named slots относительно topology selectors выбранного пула.

Canonical preview/read-model ДОЛЖЕН (SHALL) использовать slot-based projection как source-of-truth и НЕ ДОЛЖЕН (SHALL NOT) ограничиваться single `compiled_document_policy` object как единственной effective policy view.

#### Scenario: Binding preview показывает slot coverage для topology edges
- **GIVEN** binding pin-ит decisions с `decision_key=sale` и `decision_key=purchase`
- **AND** topology использует эти keys на активных edges
- **WHEN** аналитик или оператор открывает binding перед запуском
- **THEN** preview показывает pinned workflow revision, linked decisions и slot coverage summary
- **AND** пользователь видит, какие topology edges будут резолвиться каким slot'ом до старта run

#### Scenario: Preview показывает slot-based projection вместо single global policy
- **GIVEN** binding pin-ит несколько publication slots
- **WHEN** система строит preview до запуска
- **THEN** response/read-model показывает materialized slot projection и coverage summary
- **AND** effective preview не сводится к одному global compiled policy blob
