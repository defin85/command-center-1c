## MODIFIED Requirements
### Requirement: Net-new document policy authoring MUST использовать decision-resource surface
Система ДОЛЖНА (SHALL) предоставлять frontend surface на отдельном route `/decisions` для net-new `document_policy.v1` authoring через decision resources, а не через direct topology-edge editing как primary path.

Decision-resource authoring surface ДОЛЖЕН (SHALL):
- предоставлять lifecycle `list/detail/create/clone/revise/archive-deactivate` для policy-bearing decision resources;
- предоставлять structured builder для chain/documents/field_mapping/table_parts_mapping/link_rules;
- поддерживать optional raw JSON fallback без потери валидного `document_policy.v1`;
- использовать shared configuration-scoped metadata snapshots для metadata-aware validation и preview до pin в binding;
- выдавать versioned decision revision, пригодный для first-class selection в workflow/binding editor.

#### Scenario: Аналитик создаёт независимую копию существующего document policy
- **GIVEN** в `/decisions` уже существует `document_policy` revision, пригодная как seed
- **WHEN** аналитик запускает clone flow
- **THEN** editor открывается с копией source policy
- **AND** resulting publish создаёт новый decision resource с новым `decision_table_id`
- **AND** source revision не становится parent revision cloned resource

#### Scenario: Clone flow сохраняет metadata-aware validation как у net-new create
- **GIVEN** аналитик открыл clone flow для существующей revision
- **AND** в `/decisions` выбрана target database
- **WHEN** он публикует cloned policy
- **THEN** backend валидирует cloned policy против resolved metadata snapshot выбранной ИБ
- **AND** clone не обходит fail-closed metadata validation только потому, что source revision уже была опубликована
