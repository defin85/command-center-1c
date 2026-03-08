## ADDED Requirements
### Requirement: Master-data readiness preflight MUST возвращать полный список блокеров публикации
Перед переходом к публикации система MUST вычислять readiness preflight по target databases и возвращать machine-readable блокеры по canonical master-data и Organization->Party bindings.

#### Scenario: Отсутствующие bindings блокируют публикацию с диагностикой remediation-ready
- **GIVEN** run готов к публикации и для части target organizations отсутствуют `master_party` bindings
- **WHEN** выполняется readiness preflight
- **THEN** система возвращает structured blockers с указанием `organization_id`, `database_id` и типа отсутствующей связи
- **AND** переход к `publication_odata` блокируется fail-closed

### Requirement: Readiness snapshot MUST быть детерминированным и пригодным для повторной проверки
Readiness результат MUST сохраняться как стабильный snapshot для run inspection/retry, чтобы оператор видел одинаковую причину блокировки до устранения входных данных.

#### Scenario: Повторный preflight без изменений возвращает тот же набор блокеров
- **GIVEN** данные master-data и bindings не менялись
- **WHEN** preflight выполняется повторно для того же run контекста
- **THEN** snapshot blockers остаётся детерминированно эквивалентным предыдущему
