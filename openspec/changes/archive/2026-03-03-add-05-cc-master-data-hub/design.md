## Context
В текущей модели pools в CC есть каталог организаций, но нет единого канонического слоя для контрагентов, номенклатуры, договоров и налоговых профилей, которые участвуют в публикации документов.

При этом в целевых БП 3.0 ИБ данные живут в нескольких отдельных справочниках (минимум `Catalog_Организации`, `Catalog_Контрагенты`, `Catalog_Номенклатура`, `Catalog_ДоговорыКонтрагентов`), а публикационный pipeline сегодня не содержит отдельного шага master-data синхронизации перед `pool.publication_odata`.

## Goals / Non-Goals
- Goals:
  - сделать CC единой точкой ответственности за master-data, используемые в pool publication;
  - обеспечить детерминированный и идемпотентный resolve/sync master-data в каждую target ИБ;
  - исключить OData side effects при неразрешённых или неоднозначных master-data связях;
  - зафиксировать run/retry consistency через immutable snapshot.
- Non-Goals:
  - не реализовывать в этом change универсальный MDM для всех модулей платформы;
  - не переводить все существующие API в новый доменный словарь за один этап;
  - не менять экономическую/распределительную модель pool run.

## Alternatives
### Variant 1 (Recommended): Единая сущность Party + роли
- Каноническая сущность `Party` хранит базовую идентичность и атрибуты.
- Роли (`our_organization`, `counterparty`, `supplier`, `customer`) задаются отдельно и могут комбинироваться в рамках одного `Party`.
- Отдельные сущности для `Item`, `Contract`, `TaxProfile` остаются специализированными.

Плюсы:
- минимизирует дублирование для сценариев, где один участник бывает и организацией, и контрагентом;
- даёт единый ключ для междокументных связей.

Минусы:
- нужна строгая политика ownership полей и role validation.

### Variant 2: Раздельные канонические сущности Organization/Counterparty
- Повторяет структуру 1С на стороне CC.

Плюсы:
- простая ментальная модель.

Минусы:
- дублирование данных и сложные cross-entity связи;
- выше риск рассинхронизации между “тем же” субъектом в разных ролях.

## Decisions
### Decision 1: Canonical master-data слой в CC
CC хранит канонические сущности (`Party`, `Item`, `Contract`, `TaxProfile`) в tenant scope и использует их как source-of-truth для pool publication.

### Decision 2: Per-infobase binding как обязательный слой
Для каждой канонической записи хранится binding на конкретную ИБ:
- для `Party`: `canonical_id`, `entity_type`, `database_id`, `ib_catalog_kind` (`organization|counterparty`);
- для остальных сущностей: `canonical_id`, `entity_type`, `database_id`;
- `ib_ref_key` (или эквивалент внешнего ключа в ИБ);
- `sync_status`, `fingerprint`, `last_synced_at`.

Это позволяет:
- идемпотентно повторять sync;
- использовать готовые ссылки в публикации без lookup по свободному тексту.

### Decision 2.1: Единый Party в CC + role-specific bindings в ИБ
На стороне CC сохраняется единая каноническая сущность `Party`.
В момент run роль (`our_organization`/`counterparty`) определяется контекстом документа и выбирает соответствующий binding в целевом каталоге ИБ.
Один и тот же `Party` может иметь два binding в одной и той же ИБ для разных ролей.

### Decision 2.2: Contract в MVP строго owner-scoped
Сущность `Contract` в MVP ДОЛЖНА быть строго привязана к конкретному `counterparty`.
Shared contract profile на группу контрагентов в MVP НЕ допускается.
При попытке использовать договор вне owner-counterparty runtime должен завершаться fail-closed с machine-readable конфликтом.

### Decision 3: Ownership policy полей
Поля делятся на:
- `CC-owned` (канонические атрибуты, которые CC должен синхронизировать);
- `IB-local` (локальные служебные поля, которые CC не перезаписывает).

Если обновление затрагивает только `IB-local`, sync не должен ломать данные в ИБ.

### Decision 4: Pre-publication master-data gate
Перед `pool.publication_odata` runtime обязан выполнить resolve/sync gate:
1. собрать ссылки на master-data из run snapshot/document plan;
2. проверить/создать bindings в каждой target ИБ;
3. при успехе сохранить `master_data_binding_artifact`;
4. при конфликте/неоднозначности завершить run fail-closed до публикации документов.

### Decision 4.1: Режим MVP — resolve+upsert
В MVP используется режим `resolve+upsert` (а не `validate-only`):
- gate может создавать отсутствующие bindings и связанные записи в ИБ;
- поведение остаётся идемпотентным по ключу binding;
- rollout выполняется под feature-flag с возможностью переключения на `validate-only` для строгих контуров.

### Decision 5: Immutable snapshot для run/retry consistency
На старте run фиксируется `master_data_snapshot_ref`.
Любой retry использует тот же snapshot и тот же binding artifact (или детерминированно пересобирает binding только из этого snapshot), чтобы исключить drift в середине процесса.

## Contract Notes
- Publication payload должен использовать resolved reference поля (`*_Key` / `Ref_Key`) из binding artifact, а не свободный текст.
- Ошибки resolve/sync должны быть machine-readable и пригодными для operator remediation (`code`, `path`, `detail`).
- Все master-data side effects должны быть идемпотентны относительно пары `(canonical_id, database_id, entity_type)`.
- Для `Contract` ключ резолва обязан учитывать owner `counterparty`; переиспользование binding между разными контрагентами не допускается.
- Для `TaxProfile` MVP-область ограничена НДС-полями: `vat_rate`, `vat_included`, `vat_code`.

## Risks / Trade-offs
- Риск: рост сложности модели из-за role-based `Party`.
  - Mitigation: MVP-ограничение ролей и явные инварианты role compatibility.
- Риск: расхождение между CC snapshot и текущим состоянием ИБ.
  - Mitigation: immutable snapshot + fail-closed при конфликтных upsert/match.
- Риск: увеличение latency перед публикацией из-за sync gate.
  - Mitigation: кэшируемые bindings, дифф-синхронизация по fingerprint, батчирование запросов.

## Migration and Rollout
1. Ввести спецификацию и контракты capability `pool-master-data-hub`.
2. Добавить модель bindings + базовый sync/resolve для MVP-сущностей.
3. Встроить master-data gate в workflow перед `pool.publication_odata`.
4. Перевести publication payload на resolved refs из binding artifact.
5. Добавить мониторинг/диагностику и staged rollout (feature flag/canary).

## Open Questions
- Нет блокирующих открытых вопросов.
