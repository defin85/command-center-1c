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
  - не делать универсальный cross-domain MDM;
  - не добавлять сложный conflict-resolution мастер;
  - не менять доменный контракт распределения run.

## Alternatives
### Variant A: Встроить всё в `/pools/catalog` (single-page expansion)
Плюсы:
- меньше новых маршрутов.

Минусы:
- `PoolCatalogPage` уже содержит большой объём сценариев;
- высокий риск ухудшения UX и maintainability;
- сложнее локализовать ответственность команд и тестов.

### Variant B (Recommended): Отдельный маршрут `/pools/master-data` + точечная интеграция в catalog/runs
Плюсы:
- изоляция ответственности и более читаемый UX;
- проще rollout и тестирование по независимому модулю;
- меньше риск регрессий в текущем catalog flow.

Минусы:
- новые API + дополнительный route/menu.

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

Режим raw JSON сохраняется как fallback для advanced сценариев.

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
  - Mitigation: изолированный компонент picker + сохранение raw-mode.

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
