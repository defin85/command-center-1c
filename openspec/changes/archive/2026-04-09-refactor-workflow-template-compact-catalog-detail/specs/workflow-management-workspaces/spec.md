## MODIFIED Requirements

### Requirement: `/workflows` MUST использовать canonical workflow library workspace

Система ДОЛЖНА (SHALL) представлять `/workflows` как workflow library workspace с URL-addressable selected surface/filter/workflow context и shell-safe handoff в workflow authoring и execution paths.

На desktop primary master pane ДОЛЖЕН (SHALL) оставаться compact selection surface для выбора workflow и короткой runtime-or-authoring ориентации. Wide table, horizontal overflow и icon-first row action cluster НЕ ДОЛЖНЫ (SHALL NOT) быть default primary composition path workflow library.

Primary actions workflow library ДОЛЖНЫ (SHALL) быть доступны из detail-owned action cluster или через explicit route handoff, а не зависеть от dense row-level action strip как единственного discoverable path.

#### Scenario: Workflow library восстанавливает selected context из URL

- **GIVEN** оператор открывает `/workflows` с query state, указывающим surface, фильтры или выбранный workflow
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же library context
- **AND** primary navigation в designer или execute path выполняется внутри canonical workspace flow

#### Scenario: Desktop workflow library показывает compact selection catalog

- **GIVEN** оператор открывает `/workflows` на desktop viewport
- **WHEN** route рендерит primary library catalog
- **THEN** master pane показывает scan-friendly workflow selection surface с компактными status cues
- **AND** route не использует wide table с horizontal overflow как default primary workflow catalog

#### Scenario: Primary workflow actions живут в detail cluster

- **GIVEN** оператор выбрал workflow в library catalog
- **WHEN** он хочет inspect, edit, clone или execute workflow
- **THEN** эти действия доступны из detail-owned action cluster или явного route handoff
- **AND** оператору не требуется искать icon-only row actions внутри primary catalog table
