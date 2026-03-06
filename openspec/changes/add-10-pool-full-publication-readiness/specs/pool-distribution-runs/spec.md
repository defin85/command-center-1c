## ADDED Requirements
### Requirement: Pool runs MUST поддерживать профиль `minimal_documents_full_payload` для top-down acceptance
Система MUST предоставлять режим запуска, в котором количество публикуемых документов минимизируется до необходимого для активной цепочки, но каждый документ остаётся полно заполненным по заранее объявленному completeness profile.

#### Scenario: Оператор запускает top-down run с минимальным числом документов без потери полноты payload
- **GIVEN** активная topology и выбран профиль `minimal_documents_full_payload`
- **WHEN** оператор запускает run из UI
- **THEN** runtime формирует минимально необходимый набор документов для целевых узлов
- **AND** каждый документ проходит проверку полноты до перехода к `publication_odata`

### Requirement: Dev acceptance path MUST исполнять run lifecycle через live UI/API контур
Для приемки на dev система MUST поддерживать end-to-end сценарий `create -> confirm (safe) -> publish -> report` через реальные API endpoints без тестовых моков транспортного или run-пути.

#### Scenario: Run проходит полный lifecycle через UI и возвращает прозрачный отчёт
- **GIVEN** readiness блокеры отсутствуют
- **WHEN** оператор выполняет run lifecycle из UI
- **THEN** run достигает terminal статуса через реальный runtime path
- **AND** UI report отображает актуальные attempts, readiness и verification summary
