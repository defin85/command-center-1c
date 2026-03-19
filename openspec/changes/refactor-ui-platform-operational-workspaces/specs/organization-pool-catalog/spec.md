## ADDED Requirements
### Requirement: `/pools/catalog` MUST использовать task-first platform workspace composition
Система ДОЛЖНА (SHALL) реализовать `/pools/catalog` как platform workspace, где:
- catalog pools является primary context;
- pool basics, topology authoring, workflow attachment workspace и remediation guidance разделены по задаче;
- оператор может работать с attachment/edit/remediation без конкурирующего monolithic page canvas, в котором одновременно открыты все режимы.

Route ДОЛЖЕН (SHALL) сохранять selected pool, active task context и relevant secondary state в URL-addressable форме, чтобы deep-link, reload и browser back/forward сохраняли операторский контекст.

Primary mutate flows для attachment workspace НЕ ДОЛЖНЫ (SHALL NOT) оставаться raw inline mega-editor path. Они ДОЛЖНЫ (SHALL) использовать canonical form shells, platform-owned secondary surfaces или явный handoff в dedicated canonical route.

#### Scenario: Deep-link возвращает оператора в тот же pool workspace context
- **GIVEN** оператор открыл `/pools/catalog` для конкретного pool и attachment/remediation context
- **WHEN** страница перезагружается или ссылка открывается повторно
- **THEN** UI восстанавливает selected pool и task context
- **AND** оператор продолжает работу без повторного ручного выбора нужного пула и вкладки

#### Scenario: Attachment workflow не конкурирует с topology и pool basics в одном default canvas
- **GIVEN** оператору нужно изменить attachment state или пройти remediation в `/pools/catalog`
- **WHEN** он открывает соответствующий flow
- **THEN** UI переводит его в dedicated secondary surface или canonical task section
- **AND** topology, pool basics и attachment authoring не остаются одновременно primary competing flows на одном default экране
