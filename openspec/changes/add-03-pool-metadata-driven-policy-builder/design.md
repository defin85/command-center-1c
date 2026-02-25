## Context
В текущем UI `/pools/catalog` поля `Document policy (JSON)` и `Edge metadata (JSON)` заполняются вручную. Это работает для простых кейсов, но плохо масштабируется для реальных 1С-конфигураций, где:
- большое количество документов;
- разные наборы реквизитов между базами;
- табличные части имеют отдельные `RowType` и собственные реквизиты.

Итог: высокая цена ошибки и зависимость от ручного редактирования JSON.

## Goals / Non-Goals
- Goals:
  - дать оператору интерактивный builder для `document_policy` и `edge.metadata`;
  - использовать OData `$metadata` как источник обновления, а persisted snapshot в БД как source-of-truth по доступным объектам;
  - сохранить fail-closed валидацию на backend;
  - сохранить raw JSON fallback для продвинутых сценариев.
- Non-Goals:
  - не менять execution runtime и publication orchestration;
  - не строить универсальный low-code конструктор произвольных сущностей 1С;
  - не заменять действующий `document_policy.v1` на новый DSL.

## Decisions
### Decision 1: Отдельный metadata catalog read-model в backend
Добавляется read API, который возвращает нормализованную структуру:
- `documents[]`:
  - `entity_name`;
  - `display_name`;
  - `fields[]` (name, type, nullable);
  - `table_parts[]`:
    - `name`;
    - `row_fields[]` (name, type, nullable).

Источник: OData `$metadata` выбранной ИБ.

### Decision 2: Persisted metadata snapshots в БД как source-of-truth
Нормализованный metadata catalog хранится в БД в snapshot-модели. Минимальные поля snapshot:
- `tenant_id`, `database_id` (или эквивалентный infobase scope);
- `config_name`, `config_version`, `extensions_fingerprint`;
- `metadata_hash`, `catalog_version`;
- `payload` (нормализованный catalog JSON);
- `fetched_at`, `source`, `is_current`.

Правила:
- read path читает только current snapshot из БД/Redis, а не парсит CSDL в UI и не зависит от live OData при каждом запросе;
- refresh path выполняет live fetch `$metadata`, нормализацию, вычисление hash/version и атомарно переключает `is_current`;
- при отсутствии snapshot допускается cold bootstrap под lock: live fetch -> persist -> serve.

### Decision 3: Redis read-through cache как ускоритель, не источник истины
Redis используется только для ускорения чтения current snapshot:
- ключ: `(tenant_id, database_id, config_name, config_version, extensions_fingerprint)`;
- value: `snapshot_id`/`catalog_version` + компактный catalog payload;
- TTL: конфигурируемый.

Fallback:
- Redis miss/error -> чтение из current snapshot в БД;
- Redis недоступен не должен ломать корректность и fail-closed validation.

### Decision 4: Версионирование по конфигурации с контролем дрейфа
Основной version marker:
- `config_name + config_version`.

Защита от дрейфа (одинаковая версия, разный фактический состав metadata):
- обязательный `metadata_hash` от нормализованного payload;
- `catalog_version` формируется детерминированно из version markers.

### Decision 5: Builder + Raw dual-mode в UI
UI topology editor получает два режима:
- `Builder mode`: форма с выбором документов/реквизитов/табличных частей из каталога.
- `Raw JSON mode`: прямое редактирование JSON.

Режимы синхронизируются через единый внутренний state: builder генерирует канонический JSON, raw-mode может редактировать его напрямую. При ошибке парсинга в raw-mode builder блокируется до исправления.

### Decision 6: Fail-closed validation на save path
При сохранении topology snapshot backend валидирует:
- существование `entity_name` в current metadata snapshot выбранной ИБ;
- существование ключей `field_mapping` в `document.fields`;
- существование `table_parts_mapping` и `row_fields`;
- корректность ссылок между документами chain (`link_to`, `link_rules`).

Нарушения возвращаются как machine-readable validation ошибки без частичного сохранения snapshot. При отсутствии current snapshot для целевого scope/save path возвращается fail-closed ошибка.

### Decision 7: Безопасный auth-path для metadata read
Metadata read использует тот же mapping-aware подход credentials, что и publication path:
- credentials берутся из `InfobaseUserMapping`;
- fallback на `Database.username/password` запрещён;
- ошибки маппинга возвращаются fail-closed с детерминированным кодом.

## API Sketch
- `GET /api/v2/pools/odata-metadata/catalog?database_id=<id>`
  - returns normalized catalog из current snapshot + metadata (`fetched_at`, `source`, `catalog_version`, `config_name`, `config_version`, `metadata_hash`).
  - `source` отражает фактический путь ответа (`redis`, `db`, `live_refresh`).
- `POST /api/v2/pools/odata-metadata/catalog/refresh`
  - body: `database_id`;
  - live fetch `$metadata` -> persist new snapshot (если есть изменения) -> warm Redis.

Topology save endpoint сохраняет текущий контракт, но расширяет validation errors для `document_policy`/`edge.metadata` ссылок на current metadata snapshot.

## Risks / Trade-offs
- Большой CSDL может тормозить первый cold bootstrap.
  - Mitigation: background refresh, lock на bootstrap, lazy open UI section.
- Рост объёма snapshot-данных в БД.
  - Mitigation: retention policy по версиям/времени, хранение только изменившихся snapshot.
- Разные версии 1С могут иметь отличающиеся имена/типы полей.
  - Mitigation: version markers (`config_name/config_version`) + `metadata_hash`, fail-closed validation и явная диагностика в UI.
- Сложность builder UX для сложных chain.
  - Mitigation: staged UX (MVP: базовые chain + mappings) и raw fallback.

## Migration and Rollout
1. Добавить snapshot schema в БД и сервис формирования snapshot из live `$metadata`.
2. Включить refresh-path с атомарным переключением current snapshot.
3. Включить read API: Redis hit -> DB fallback -> (опционально) cold bootstrap.
4. Добавить UI загрузку каталога и read-only preview.
5. Добавить interactive builders для document policy и edge metadata.
6. Включить строгую backend validation ссылок на current metadata snapshot.
7. Обновить операторскую/операционную документацию и провести rollout на staging.
