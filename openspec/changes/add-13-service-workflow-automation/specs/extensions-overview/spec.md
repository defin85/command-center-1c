## MODIFIED Requirements
### Requirement: Обзор расширений по всем базам
Система ДОЛЖНА (SHALL) использовать `/extensions` как domain surface для service operations домена extensions.

Экран ДОЛЖЕН (SHALL) поддерживать:
- direct template/manual execution там, где это уместно;
- curated workflow launch через binding `service_action -> workflow` для reusable automation сценариев.

Action-catalog path при этом по-прежнему НЕ ДОЛЖЕН (SHALL NOT) использоваться.

#### Scenario: Пользователь запускает curated workflow из `/extensions`
- **GIVEN** для `service_action="extensions.install"` настроен workflow binding
- **WHEN** пользователь инициирует установку расширения из `/extensions`
- **THEN** UI запускает связанный workflow path
- **AND** пользователь остаётся в domain UX без перехода в raw workflow catalog

## ADDED Requirements
### Requirement: `/extensions` MUST сохранять domain lineage при workflow-based service actions
Система ДОЛЖНА (SHALL) в `/extensions` показывать для workflow-based service action domain-friendly статус и ссылку на underlying workflow execution diagnostics.

#### Scenario: Extension action details показывают и domain статус, и workflow lineage
- **GIVEN** пользователь запустил workflow-based `extensions.install`
- **WHEN** открывает details операции из `/extensions`
- **THEN** UI показывает доменный статус действия
- **AND** дополнительно показывает ссылку на связанный workflow revision/execution как secondary diagnostics
