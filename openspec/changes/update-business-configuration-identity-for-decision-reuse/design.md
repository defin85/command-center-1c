## Context
Сейчас система использует configuration-scoped metadata snapshot contract, в котором identity фактически строится из:
- `config_name`;
- `config_version`;
- `extensions_fingerprint`;
- `metadata_hash`.

В коде `config_name` вычисляется из `database.base_name || database.infobase_name || database.name`, а `config_version` из `Database.version`. Это хорошо работает как database-local heuristic, но не как бизнес-идентичность прикладного решения.

Одновременно `metadata_hash` считается от опубликованного OData payload. По документам 1C published OData composition определяется publication settings и `SetStandardODataInterfaceContent`, то есть зависит от operational publication state, а не только от версии конфигурации.

Проверка на живой выгрузке БП 3.0 подтвердила, что root `Configuration.xml` уже содержит нужные business properties:
- `Name`
- `Synonym`
- `Vendor`
- `Version`

Это и есть корректный source-of-truth для business identity конфигурации.

## Goals
- Использовать business identity конфигурации как compatibility/reuse key для shared metadata snapshots и `decision_revision`.
- Получать identity из root configuration properties через существующий Designer path.
- Убрать зависимость reuse от имени ИБ.
- Перевести `metadata_hash` и связанные operational markers в diagnostics/provenance слой.
- Сохранить analyst-facing reuse `decision_revision` между ИБ одной и той же конфигурации даже при publication drift.

## Non-Goals
- Не определять в этом change полный support workflow исправления OData publication у tenant.
- Не использовать `metadata_hash`, `config_generation_id` или `extensions_fingerprint` как новые blocking compatibility keys.
- Не вводить dependence на OData как источник business identity конфигурации.
- Не менять route structure `/decisions` или `/pools/catalog` вне identity/provenance semantics.

## Decision 1: Business identity конфигурации равна `config_name + config_version`
Нормативная configuration identity для metadata snapshot reuse и compatibility `decision_revision` фиксируется как:
- `config_name`
- `config_version`

Под `config_name` в этом change понимается business-level имя конфигурации, а не имя ИБ.

Имя ИБ, `database_id`, `metadata_hash`, `extensions_fingerprint` и `config_generation_id` НЕ ДОЛЖНЫ (SHALL NOT) участвовать в reuse/compatibility key.

## Decision 2: Источник истины для `config_name` и `config_version` только root configuration properties
Business identity конфигурации должна сниматься через существующий Designer path, используя root configuration export/properties.

Минимальный нормативный source-of-truth:
- `config_name`: root configuration `Synonym` в предпочтительной локали `ru`; если подходящий `Synonym` отсутствует, допускается fallback к первому доступному synonym entry; если synonym недоступен, допускается fallback к root `Name`.
- `config_version`: root configuration `Version`.

Система не должна:
- брать `config_name` из `Database.base_name`, `Database.infobase_name` или `Database.name`;
- брать `config_version` из `Database.version`;
- выводить business identity из OData payload;
- подменять её `config_generation_id`.

Причина: именно root configuration properties соответствуют тому, что 1C считает application properties/release details.

## Decision 3: `metadata_hash`, `extensions_fingerprint` и `config_generation_id` становятся diagnostics-only markers
Эти markers остаются полезными, но меняют роль:
- `metadata_hash` описывает publication surface;
- `extensions_fingerprint` описывает technical applicability/customization state;
- `config_generation_id` описывает technical metadata generation;
- имя ИБ и provenance database описывают operational source.

Они должны сохраняться и возвращаться в API/read-model, но:
- не участвуют в shared snapshot reuse key;
- не образуют hard incompatibility для `decision_revision`;
- не скрывают compatible revision из default `/decisions` path.

## Decision 4: Publication drift non-blocking для reuse, но остаётся видимой диагностикой
Если две ИБ имеют одинаковые `config_name + config_version`, но разный published OData payload, система должна считать их business-compatible для reuse metadata snapshots и `decision_revision`.

При этом publication drift не должен исчезать:
- read-model должен показывать, что selected infobase diverges от canonical/shared publication state;
- `/decisions` и related selectors должны показывать warning/diagnostics;
- drift не должен переводить revision в incompatible только сам по себе.

Это соответствует business policy: за неполную публикацию отвечает support/operations слой, а не analyst-facing compatibility contract.

## Decision 5: Shared snapshot registry остаётся canonical, но scope становится business-level
Canonical metadata snapshot registry по-прежнему нужен как reusable read-model для builder/preview.

Но теперь canonical scope определяется business identity `config_name + config_version`, а не publication hash.

Практический смысл:
- selected database остаётся auth/probe source и provenance anchor;
- canonical snapshot может быть подтверждён другой ИБ той же конфигурации;
- infobase с неполной publication может использовать canonical snapshot peer-ИБ той же business identity.

## Decision 6: Decision compatibility и selector filtering используют только business identity
`Decision revision` для `document_policy` должна считаться business-compatible, если текущий context и stored context совпадают по `config_name + config_version`.

Следствия:
- разные имена ИБ не должны ломать compatibility;
- разный `metadata_hash` не должен делать revision incompatible;
- `config_generation_id` и `extensions_fingerprint` не должны участвовать в filtering/selectability;
- stored provenance markers остаются в UI/read-model как auditable diagnostics.

## Risks / Trade-offs
- Плюс: analyst-facing reuse соответствует реальному бизнес-ожиданию “одна конфигурация, один релиз”.
- Плюс: исчезает ложная несовместимость из-за имени ИБ.
- Плюс: исчезает ложная несовместимость из-за publication drift.
- Минус: система перестаёт fail-closed блокировать reuse при неидеальной публикации OData.
- Минус: `Synonym` локализован; нужен детерминированный fallback порядок.
- Минус: старые snapshots/revisions, сохранённые по legacy semantics, потребуют migration/backfill.

## Migration / Rollout
1. Зафиксировать новый contract в specs и OpenAPI/read-model.
2. Добавить Designer-based extraction root configuration properties.
3. Перевести snapshot scope/resolution и decision compatibility на `config_name + config_version`.
4. Сохранить legacy markers как diagnostics-only provenance.
5. Выполнить migration/backfill текущих snapshot/revision metadata contexts на новую semantics.
6. Обновить `/decisions` filtering и rollover flow на новый business compatibility contract.

## Open Questions
- Нет блокирующих. В рамках этого change принимается явное решение пользователя: compatibility/reuse key ограничивается только связкой “конфигурация + её версия”.
