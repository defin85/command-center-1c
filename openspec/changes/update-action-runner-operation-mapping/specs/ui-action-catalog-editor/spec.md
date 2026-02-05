## MODIFIED Requirements

### Requirement: Save с серверной валидацией и отображением ошибок
Система ДОЛЖНА (SHALL) сохранять изменения через backend и показывать ошибки валидации пользователю; UI НЕ ДОЛЖЕН (SHALL NOT) вводить дополнительные ограничения, которые не требуются backend (например, блокировать дубли reserved capability), если backend допускает такие конфигурации.

#### Scenario: UI не блокирует сохранение из-за duplicate reserved capability
- **GIVEN** staff добавляет второй action с `capability="extensions.set_flags"`
- **WHEN** staff нажимает Save
- **THEN** UI отправляет payload на backend и показывает результат
- **AND** если backend вернул ошибки, UI показывает их с путями вида `extensions.actions[i]...`

