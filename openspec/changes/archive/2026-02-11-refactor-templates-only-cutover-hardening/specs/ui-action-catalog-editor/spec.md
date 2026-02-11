## ADDED Requirements
### Requirement: Templates-only baseline MUST быть закреплён в тестах и операторской документации
Система ДОЛЖНА (SHALL) исключить из regression baseline указания и ожидания, которые трактуют Action Catalog как рабочий UI flow.

#### Scenario: Browser regression suite не использует legacy Action Catalog flow
- **WHEN** выполняются browser tests для `/templates`, `/extensions`, `/databases`
- **THEN** тестовые сценарии не используют `surface=action_catalog`
- **AND** не ожидают вызовов `/api/v2/ui/action-catalog/` как штатного runtime path

#### Scenario: Операторские инструкции не содержат legacy route как рабочий сценарий
- **WHEN** оператор читает актуальные runbooks/guides по manual operations
- **THEN** документация не направляет в `/templates?surface=action_catalog` как рабочий путь
- **AND** основной сценарий описан через templates-only manual operations модель
