## ADDED Requirements
### Requirement: Organization catalog MUST иметь явный binding к canonical Party
Система ДОЛЖНА (SHALL) поддерживать явный binding между `Organization` и `Party` (MVP `1:1`) для устранения дублирования источников истины.

Система ДОЛЖНА (SHALL) применять ownership policy:
- `Organization` владеет topology/pool-catalog полями;
- `Party` владеет каноническими master-data реквизитами, используемыми publication runtime.

Система ДОЛЖНА (SHALL) выполнять backfill `Organization -> Party` детерминированно:
- match-кандидаты определяются по `(tenant_id, inn, is_our_organization=true)` и дополнительно по `kpp`, если `Organization.kpp` непустой;
- при ровно одном кандидате binding создаётся автоматически;
- при `0` или `>1` кандидате binding не создаётся, запись попадает в remediation-list.

Система НЕ ДОЛЖНА (SHALL NOT) допускать публикационные сценарии, требующие `our_organization` role, без валидного `Organization -> Party` binding.

#### Scenario: Existing organization получает canonical Party binding в миграции
- **GIVEN** в tenant уже есть записи `Organization` до включения master-data workspace
- **WHEN** выполняется rollout с backfill `Organization -> Party`
- **THEN** каждая организация получает валидный binding или попадает в явный remediation-list
- **AND** система не создаёт silent fallback соответствия

#### Scenario: Публикационный preflight блокируется при отсутствии binding
- **GIVEN** организация участвует в topology/pool run
- **AND** для неё отсутствует валидный `Organization -> Party` binding
- **WHEN** система выполняет pre-publication checks для run
- **THEN** run блокируется fail-closed до OData side effects
- **AND** оператор получает machine-readable диагностику с контекстом организации

#### Scenario: Неоднозначный backfill не создаёт автоматический binding
- **GIVEN** для одной `Organization` найдено несколько `Party`-кандидатов по tenant/INN
- **WHEN** выполняется backfill `Organization -> Party`
- **THEN** binding не создаётся автоматически
- **AND** организация добавляется в remediation-list для ручного исправления
