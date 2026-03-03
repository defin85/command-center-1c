## ADDED Requirements
### Requirement: Workflow enqueue MUST валидировать scheduling contract для sync workload
Система ДОЛЖНА (SHALL) принимать workflow enqueue для sync workload только при валидном scheduling contract:
- `priority` из поддерживаемого enum;
- `role` из поддерживаемого enum;
- `server_affinity` не пустой;
- `deadline_at` в RFC3339 UTC.

Система НЕ ДОЛЖНА (SHALL NOT) публиковать enqueue-команду в stream при невалидном scheduling payload.

#### Scenario: Невалидный scheduling payload блокирует enqueue
- **GIVEN** enqueue workflow execution содержит некорректный `priority` или пустой `server_affinity`
- **WHEN** система выполняет pre-enqueue валидацию
- **THEN** возвращается ошибка валидации с machine-readable кодом
- **AND** root operation projection не переходит в `queued`
- **AND** stream-команда не публикуется

### Requirement: Workflow queue processing MUST сохранять observability scheduling полей
Система ДОЛЖНА (SHALL) сохранять `priority`, `role`, `server_affinity`, `deadline_at` в operation metadata и event/timeline payload для последующей диагностики SLA.

#### Scenario: Scheduling метаданные доступны в operations/timeline
- **GIVEN** workflow execution поставлен в очередь с валидным scheduling contract
- **WHEN** оператор запрашивает operation details или timeline события
- **THEN** response/events содержат согласованные `priority`, `role`, `server_affinity`, `deadline_at`
- **AND** значения пригодны для фильтрации backlog и latency аналитики
