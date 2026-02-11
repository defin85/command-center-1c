## MODIFIED Requirements
### Requirement: Templates API MUST использовать unified persistent store
Система ДОЛЖНА (SHALL) управлять templates через unified management API `operation-catalog` (`surface="template"`), а не через persistent projection `OperationTemplate`.

При этом внешний контракт ДОЛЖЕН (SHALL) оставаться backward-compatible по identifier naming (`template_id`, `operation_templates` в API-полях/ответах, где это уже зафиксировано клиентами).

#### Scenario: Management API возвращает template по alias с прежним template_id
- **GIVEN** template опубликован как `operation_exposure(surface="template", alias="tpl-sync-default")`
- **WHEN** клиент запрашивает список/детали templates
- **THEN** в ответе используется `template_id="tpl-sync-default"` (или эквивалентный id поля в текущем контракте)
- **AND** данные шаблона читаются из `operation_exposure + operation_definition`

### Requirement: Templates RBAC MUST сохраниться при переходе на unified persistence
Система ДОЛЖНА (SHALL) сохранить текущие ограничения доступа templates API (view/manage) после перехода на exposure-only модель.

Template RBAC НЕ ДОЛЖЕН (SHALL NOT) зависеть от FK на `OperationTemplate` после cutover.
Template RBAC ДОЛЖЕН (SHALL) храниться в exposure-ориентированных permission-структурах (`user/group -> exposure`) и использоваться в `rbac`/`effective-access` endpoint'ах.

#### Scenario: Проверка прав работает без OperationTemplate rows
- **GIVEN** legacy `operation_templates` projection удалён
- **WHEN** пользователь запрашивает templates list или выполняет template upsert/delete
- **THEN** система вычисляет доступ через exposure-ориентированные шаблонные права
- **AND** решение по доступу совпадает с ожидаемым view/manage уровнем

#### Scenario: Effective access резолвится через exposure permissions
- **GIVEN** у пользователя заданы прямые и групповые template права
- **WHEN** вызывается endpoint effective access
- **THEN** итоговый уровень доступа рассчитывается без чтения `OperationTemplate*Permission`
- **AND** результат соответствует прежней семантике max(view/manage/admin)

## ADDED Requirements
### Requirement: Workflow operation runtime MUST резолвить template через OperationExposure alias
Система ДОЛЖНА (SHALL) в operation-node execution path резолвить template по `OperationExposure(surface="template", alias=node.template_id)` и использовать связанный `OperationDefinition` для формирования исполняемого payload.

Runtime ДОЛЖЕН (SHALL) работать fail-closed: при неуспешном resolve exposure fallback к `OperationTemplate` НЕ ДОЛЖЕН (SHALL NOT) выполняться.

#### Scenario: Operation node выполняется без OperationTemplate.objects.get
- **GIVEN** в workflow node указан `template_id="tpl-odata-create"`
- **WHEN** workflow engine запускает operation node
- **THEN** шаблон и execution payload получаются из exposure/definition модели
- **AND** runtime не вызывает `OperationTemplate.objects.get`

#### Scenario: Missing alias отклоняется fail-closed
- **GIVEN** в workflow node указан `template_id`, отсутствующий в `operation_exposure(surface="template")`
- **WHEN** workflow engine выполняет resolve template
- **THEN** выполнение завершается ошибкой `TEMPLATE_NOT_FOUND` (или эквивалентным fail-closed кодом)
- **AND** enqueue операции не выполняется
- **AND** fallback на `OperationTemplate` не выполняется

#### Scenario: Inactive или unpublished exposure отклоняется fail-closed
- **GIVEN** exposure найден, но `is_active=false` или `status!=published`
- **WHEN** runtime пытается выполнить operation node
- **THEN** выполнение завершается ошибкой `TEMPLATE_NOT_PUBLISHED` (или эквивалентным fail-closed кодом)
- **AND** fallback на legacy projection не выполняется

### Requirement: Internal template endpoints MUST работать через exposure-only read path
Система ДОЛЖНА (SHALL) обслуживать internal template read/render endpoint'ы через `OperationExposure + OperationDefinition` и не требовать существования legacy `OperationTemplate`.

#### Scenario: Internal get-template возвращает template после удаления legacy projection
- **GIVEN** `operation_templates` таблица удалена после cutover
- **WHEN** internal service запрашивает `get-template` по `template_id`
- **THEN** endpoint возвращает template contract с данными из exposure/definition
- **AND** статус ответа остаётся совместимым с текущим internal API

### Requirement: Big-bang switch MUST завершать dual-read/dual-write режим
Система ДОЛЖНА (SHALL) после switch-фазы отключить dual-read/dual-write на `OperationTemplate` в templates контуре.

#### Scenario: Post-switch запись template не создаёт legacy projection
- **WHEN** пользователь создаёт или обновляет template после cutover
- **THEN** изменяются только `operation_definition` и `operation_exposure`
- **AND** попытка читать/писать `OperationTemplate` не выполняется
