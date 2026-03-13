## ADDED Requirements
### Requirement: `/decisions` MUST hand off metadata management to `/databases`
Система ДОЛЖНА (SHALL) сохранять `/decisions` как metadata-aware decision lifecycle surface, но НЕ ДОЛЖНА (SHALL NOT) превращать его в primary operator surface для configuration profile или metadata snapshot maintenance.

`/decisions` ДОЛЖЕН (SHALL):
- показывать resolved target metadata context в read-only виде;
- различать проблемы business identity/profile и проблемы current snapshot;
- при отсутствии или устаревании metadata context давать явный CTA/handoff в `/databases`.

Система НЕ ДОЛЖНА (SHALL NOT) ограничиваться generic сообщением о необходимости "reload database-specific metadata" без указания canonical management surface.

#### Scenario: Metadata context unavailable -> UI направляет в `/databases`
- **GIVEN** аналитик открыл `/decisions` для базы, у которой отсутствует current metadata context
- **WHEN** UI блокирует edit/deactivate/rollover fail-closed
- **THEN** сообщение объясняет, что metadata management выполняется через `/databases`
- **AND** аналитик получает явный CTA/handoff вместо неадресного reload-сообщения

#### Scenario: `/decisions` остаётся consumer surface, а не mutate hub
- **GIVEN** аналитик просматривает metadata context выбранной ИБ в `/decisions`
- **WHEN** ему требуется metadata maintenance action
- **THEN** экран использует `/databases` как canonical handoff
- **AND** `/decisions` не становится primary местом для refresh/re-verify controls
