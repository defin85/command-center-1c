## Context
Backend часть `add-05-cc-master-data-hub` уже присутствует в кодовой базе:
- канонические модели `PoolMasterParty/Item/Contract/TaxProfile/Binding`;
- pre-publication шаг `pool.master_data_gate`;
- fail-closed diagnostics.

Проблема: отсутствует полноценный operator-facing UI для управления этими данными и для быстрой диагностики gate-ошибок в run inspection.

## Goals / Non-Goals
- Goals:
  - дать оператору единый workspace для master-data в pools;
  - убрать ручной ввод master-data токенов в document policy;
  - сделать `master_data_gate` диагностику читаемой и actionable в UI;
  - поддержать staged rollout через runtime setting override.
- Non-Goals:
  - не расширять scope change за пределы pools runtime/UI контура;
  - не добавлять сложный conflict-resolution мастер;
  - не менять доменный контракт распределения run.

## Target Architecture Path
Для этого change зафиксирован единый путь реализации:
- отдельный workspace `/pools/master-data`;
- точечная интеграция в `/pools/catalog` (token picker) и `/pools/runs` (gate diagnostics card);
- единые backend/API контракты под этот UI-модуль.

## Decisions
### Decision 1: Выделить отдельный workspace `/pools/master-data`
UI предоставляет 5 рабочих зон (tabs):
- `Party`;
- `Item`;
- `Contract`;
- `TaxProfile`;
- `Bindings`.

Каждая зона имеет table + filter + create/edit drawer с валидацией доменных инвариантов.

### Decision 2: Развести ответственность `Organization` и `Party` через явный binding
Чтобы устранить конфликт source-of-truth:
- `Organization` остаётся доменной сущностью topology/pool-catalog;
- `Party` остаётся канонической мастер-сущностью publication слоя.

MVP вводит явную связь `Organization <-> Party` (один-к-одному) с инвариантами:
- связанный `Party` для `Organization` обязан иметь `is_our_organization=true`;
- без валидной связи mutating flows, где требуется publication master-data, блокируются fail-closed.

Политика ownership полей:
- `Party-owned`: юридические реквизиты и publication-атрибуты;
- `Organization-owned`: технические поля каталога/топологии.

### Decision 3: Сохранить unified `Party` и enforce role-specific/owner-scoped контракты в UI
- `Party` редактируется как единая сущность с role flags.
- `Bindings` для `Party` требуют `ib_catalog_kind=organization|counterparty`.
- `Contract` создаётся только с `owner_counterparty`, owner выбирается из Party с ролью `counterparty`.

### Decision 4: Token authoring в document policy переводится на guided picker
В `/pools/catalog` для `field_mapping` и `table_parts_mapping` добавляется режим token picker:
- выбор типа сущности (`party/item/contract/tax_profile`);
- выбор canonical_id;
- выбор qualifier (роль/owner) при необходимости;
- генерация canonical token строки.

### Decision 5: Run inspection получает явный `master_data_gate` read-model
`GET /api/v2/pools/runs/{run_id}` и `.../report` возвращают стабилизированный блок:
- `status`, `mode`,
- `targets_count`, `bindings_count`,
- `error_code`, `detail`,
- `diagnostic` (entity/database context).

UI отображает это в отдельной карточке с remediation hints.

### Decision 6: Feature control через runtime settings overrides с явной precedence
Поддерживается ключ `pools.master_data.gate_enabled` в runtime settings override модели.
Effective значение вычисляется по правилу:
1. tenant override;
2. global runtime setting;
3. env default (`POOL_RUNTIME_MASTER_DATA_GATE_ENABLED`).

Это effective значение используется для поведения gate и отображается в UI.

## Closed Implementation Decisions
### API namespace and operations are fixed
Master-data API фиксируется в namespace `/api/v2/pools/master-data/` с ресурсными группами:
- `parties`,
- `items`,
- `contracts`,
- `tax-profiles`,
- `bindings`.

Для каждой группы фиксируются операции:
- `GET /api/v2/pools/master-data/<group>/` (list + filters + pagination);
- `GET /api/v2/pools/master-data/<group>/{id}/` (get);
- `POST /api/v2/pools/master-data/<group>/upsert/` (create/update).

OpenAPI operationId фиксируется по шаблону:
- `v2_pools_master_data_<group>_list`,
- `v2_pools_master_data_<group>_get`,
- `v2_pools_master_data_<group>_upsert`.

### `master_data_gate` read-model shape is fixed
В `GET /api/v2/pools/runs/{run_id}` и `GET /api/v2/pools/runs/{run_id}/report` блок передаётся в `run.master_data_gate` со схемой:
- `status`: `completed | failed | skipped`;
- `mode`: `resolve_upsert`;
- `targets_count`: integer;
- `bindings_count`: integer;
- `error_code`: string|null;
- `detail`: string|null;
- `diagnostic`: object|null.

Для historical run без шага `pool.master_data_gate` возвращается `run.master_data_gate = null`.

### `Organization <-> Party` storage and backfill are fixed
MVP `1:1` реализуется через явный nullable binding на стороне `Organization` (`organization.master_party_id`), с инвариантами:
- binding только внутри одного tenant;
- `master_party.is_our_organization=true`.

Backfill выполняется детерминированно:
1. кандидаты ищутся по `(tenant_id, inn, is_our_organization=true)` и дополнительному сравнению `kpp` при непустом `Organization.kpp`;
2. если найден ровно один кандидат — binding заполняется автоматически;
3. если кандидат не найден или кандидатов несколько — binding остаётся `null`, запись включается в remediation-list (без silent fallback).

### Runtime flag wiring is fixed
Gate-flag читается через effective resolver по ключу `pools.master_data.gate_enabled` с precedence:
1. tenant override;
2. global runtime setting;
3. env default.

Если effective значение ключа не приводится к bool, система работает fail-closed:
- шаг `pool.master_data_gate` завершается ошибкой с machine-readable кодом `MASTER_DATA_GATE_CONFIG_INVALID`;
- публикация в OData не начинается.

### Token authoring behavior is fixed
В builder для `field_mapping` и `table_parts_mapping` вводится явный `source_type`:
- `expression` (ручной source string для немастер-выражений);
- `master_data_token` (обязательный picker, генерирующий canonical token).

Ручной ввод canonical `master_data.*` токена в `expression` режиме считается валидационной ошибкой UI.

### Rollout and rollback gates are fixed
Rollout фиксируется как staged:
1. deploy схемы/endpoint-ов с выключенным `pools.master_data.gate_enabled`;
2. backfill + remediation-list;
3. включение на pilot tenant;
4. расширение на остальные tenant.

Rollback:
- оперативный: tenant override `pools.master_data.gate_enabled=false`;
- релизный: откат backend/frontend версии без удаления миграционных данных binding.

## API / Contract Notes
- Mutating API остаётся tenant-scoped и использует machine-readable ошибки.
- Контракт ошибок для master-data UI должен быть совместим с fail-closed кодами:
  - `MASTER_DATA_ENTITY_NOT_FOUND`,
  - `MASTER_DATA_BINDING_AMBIGUOUS`,
  - `MASTER_DATA_BINDING_CONFLICT`.
- Для новых master-data mutating/read API применяется единый `application/problem+json` контракт (Problem Details), совместимый с текущими pool mutating endpoint-ами.
- OpenAPI source-of-truth фиксируется в `contracts/orchestrator/src/**`.

## Risks / Trade-offs
- Риск: дублирование валидации между UI и backend.
  - Mitigation: backend остаётся source-of-truth; UI валидация только preflight/UX.
- Риск: инциденты из-за переключения gate в tenant override.
  - Mitigation: явный effective status в UI + audit trail runtime settings.
- Риск: усложнение `PoolCatalogPage` при token picker integration.
  - Mitigation: изолированный компонент picker и отдельные UI-тесты на policy authoring.

## Rollout
1. Контракты и backend endpoints.
2. Введение и backfill `Organization <-> Party` binding.
3. Новый UI workspace route.
4. Token picker integration в catalog.
5. Run diagnostics panel.
6. Включение runtime setting toggle по tenant и staged rollout.

## Assumptions
- `add-05-cc-master-data-hub` применяется как базовая зависимость до этого change.
- В MVP достаточно CRUD/upsert и scoped filters; массовый импорт master-data не входит в scope.
