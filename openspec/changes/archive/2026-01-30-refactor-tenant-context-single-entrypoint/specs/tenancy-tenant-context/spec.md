## ADDED Requirements

### Requirement: Tenant context имеет единую точку ответственности
Система ДОЛЖНА (SHALL) устанавливать tenant context для каждого API запроса через один механизм (single entrypoint), не дублируя логику в отдельных view/permissions.

#### Scenario: Единый источник tenant context
- **GIVEN** пользователь выполняет запрос к tenant-scoped API
- **WHEN** запрос аутентифицирован
- **THEN** tenant context доступен как `request.tenant_id` (и согласован с ORM tenant-scoping, если он используется)

### Requirement: Алгоритм выбора tenant детерминирован
Система ДОЛЖНА (SHALL) выбирать tenant в следующем порядке приоритета:
1) `X-CC1C-Tenant-ID` header (если задан),
2) сохранённый active tenant пользователя,
3) первый доступный membership.

#### Scenario: Header имеет приоритет
- **GIVEN** пользователь является member tenant A и tenant B
- **WHEN** он вызывает API с `X-CC1C-Tenant-ID=tenant B`
- **THEN** запрос исполняется в tenant B

### Requirement: Membership enforcement
Система ДОЛЖНА (SHALL) запрещать выполнение запросов в tenant без membership.

#### Scenario: Нет доступа к чужому tenant
- **GIVEN** пользователь не является member tenant B
- **WHEN** он выполняет запрос с `X-CC1C-Tenant-ID=tenant B`
- **THEN** API возвращает 403

