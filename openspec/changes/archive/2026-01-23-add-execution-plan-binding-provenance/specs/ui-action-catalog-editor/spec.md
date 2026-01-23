## ADDED Requirements
### Requirement: Preview execution plan в редакторе action catalog
Система ДОЛЖНА (SHALL) предоставить в staff-only редакторе `ui.action_catalog` возможность сделать preview для выбранного action и увидеть:
- Execution Plan (в masked виде),
- Binding Provenance (источники и места подстановки),
без раскрытия секретов.

#### Scenario: Staff видит preview plan+provenance для ibcmd_cli
- **WHEN** staff выбирает action с `executor.kind=ibcmd_cli` и нажимает Preview
- **THEN** UI отображает `argv_masked[]` и список биндингов (включая пометки `resolve_at=api|worker`)

#### Scenario: Staff видит preview plan+provenance для workflow
- **WHEN** staff выбирает action с `executor.kind=workflow` и нажимает Preview
- **THEN** UI отображает `workflow_id`, `input_context_masked` и список биндингов

