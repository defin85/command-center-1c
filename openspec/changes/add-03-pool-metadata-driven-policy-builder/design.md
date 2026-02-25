## Context
В текущем UI `/pools/catalog` поля `Document policy (JSON)` и `Edge metadata (JSON)` заполняются вручную. Это работает для простых кейсов, но плохо масштабируется для реальных 1С-конфигураций, где:
- большое количество документов;
- разные наборы реквизитов между базами;
- табличные части имеют отдельные `RowType` и собственные реквизиты.

Итог: высокая цена ошибки и зависимость от ручного редактирования JSON.

## Goals / Non-Goals
- Goals:
  - дать оператору интерактивный builder для `document_policy` и `edge.metadata`;
  - использовать OData `$metadata` как source-of-truth по доступным объектам;
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

### Decision 2: Cache-first metadata retrieval с ручным refresh
Из-за большого размера `$metadata` добавляется cache-first стратегия:
- ключ: `(tenant_id, database_id, auth_context_kind)`;
- payload: нормализованный metadata catalog + `fetched_at` + `catalog_version`;
- TTL: конфигурируемый;
- ручной refresh endpoint для принудительного обновления.

Если endpoint не отдает `ETag`/`Last-Modified`, freshness контролируется TTL и manual refresh.

### Decision 3: Builder + Raw dual-mode в UI
UI topology editor получает два режима:
- `Builder mode`: форма с выбором документов/реквизитов/табличных частей из каталога.
- `Raw JSON mode`: прямое редактирование JSON.

Режимы синхронизируются через единый внутренний state: builder генерирует канонический JSON, raw-mode может редактировать его напрямую. При ошибке парсинга в raw-mode builder блокируется до исправления.

### Decision 4: Fail-closed validation на save path
При сохранении topology snapshot backend валидирует:
- существование `entity_name` в metadata catalog выбранной ИБ;
- существование ключей `field_mapping` в `document.fields`;
- существование `table_parts_mapping` и `row_fields`;
- корректность ссылок между документами chain (`link_to`, `link_rules`).

Нарушения возвращаются как machine-readable validation ошибки без частичного сохранения snapshot.

### Decision 5: Безопасный auth-path для metadata read
Metadata read использует тот же mapping-aware подход credentials, что и publication path:
- credentials берутся из `InfobaseUserMapping`;
- fallback на `Database.username/password` запрещён;
- ошибки маппинга возвращаются fail-closed с детерминированным кодом.

## API Sketch
- `GET /api/v2/pools/odata-metadata/catalog?database_id=<id>`
  - returns normalized catalog + cache metadata (`fetched_at`, `source`, `catalog_version`).
- `POST /api/v2/pools/odata-metadata/catalog/refresh`
  - body: `database_id`;
  - force refresh of cache entry.

Topology save endpoint сохраняет текущий контракт, но расширяет validation errors для `document_policy`/`edge.metadata` ссылок на metadata catalog.

## Risks / Trade-offs
- Большой CSDL может тормозить первый cold fetch.
  - Mitigation: cache + manual refresh + lazy open UI section.
- Разные версии 1С могут иметь отличающиеся имена/типы полей.
  - Mitigation: fail-closed validation и явная диагностика в UI.
- Сложность builder UX для сложных chain.
  - Mitigation: staged UX (MVP: базовые chain + mappings) и raw fallback.

## Migration and Rollout
1. Включить metadata read API и cache (без UI изменений).
2. Добавить UI загрузку каталога и read-only preview.
3. Добавить interactive builders для document policy и edge metadata.
4. Включить строгую backend validation ссылок на metadata.
5. Обновить операторскую документацию и провести rollout на staging.
