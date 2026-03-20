## ADDED Requirements
### Requirement: `/pools/binding-profiles` MUST быть operator-first workspace с shareable catalog context
Система ДОЛЖНА (SHALL) поддерживать `/pools/binding-profiles` как stateful operator workspace, где catalog context можно адресовать через URL, а detail pane сначала объясняет смысл профиля и доступные действия, а уже потом показывает низкоуровневые pins и raw payload.

Default route path ДОЛЖЕН (SHALL):
- синхронизировать search query, selected profile и detail-open state с URL;
- иметь устойчиво подписанный search control;
- использовать keyboard-first semantic profile selection;
- показывать summary, usage context и next actions раньше opaque revision IDs и raw JSON payload.

#### Scenario: Deep link восстанавливает catalog selection и search
- **GIVEN** оператор открыл `/pools/binding-profiles` с query params поиска и выбранного profile
- **WHEN** страница инициализируется или пользователь использует back/forward
- **THEN** UI восстанавливает тот же catalog context
- **AND** не сбрасывает search и selected profile на состояние по умолчанию

#### Scenario: Detail pane сначала объясняет профиль, а затем раскрывает payload
- **GIVEN** оператор выбрал reusable binding profile
- **WHEN** detail pane открылся на default path
- **THEN** верхняя часть detail показывает summary, status, workflow context и next actions
- **AND** opaque pins и raw JSON остаются доступными только как secondary/advanced layer

#### Scenario: Выбор profile не зависит только от клика по строке
- **GIVEN** оператор работает с catalog через клавиатуру
- **WHEN** он переходит по списку reusable profiles
- **THEN** UI предоставляет semantic selection trigger и явное selected state
- **AND** row click, если остаётся, работает только как дополнительное удобство
