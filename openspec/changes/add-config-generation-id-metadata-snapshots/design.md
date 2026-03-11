## Context
Существующий metadata snapshot path уже решает две разные задачи:
- canonical shared snapshot OData metadata surface;
- read-model/provenance для выбранной ИБ в `/pools/catalog` и `/decisions`.

`config_version` сейчас приходит не из OData, а из `Database.version`, и поэтому часто пустой. Проверка на живой ИБ показала, что standard OData не отдаёт человекочитаемую версию конфигурации. Одновременно в системе уже есть рабочий execution path для `designer_cli`, а в `config/cli_commands.json` уже присутствует `GetConfigGenerationID`.

Это позволяет добавить platform-level marker текущего metadata state без нового runtime surface.

## Goals
- Получать `config_generation_id` через уже существующий Designer path.
- Возвращать его в metadata read-model и decision metadata context как отдельный technical marker.
- Не смешивать его с `config_version`.
- Не менять canonical shared snapshot identity и текущую `metadata_hash`-based reuse semantics.

## Non-Goals
- Не получать user-facing business version конфигурации.
- Не вводить extension/RAS fallback path.
- Не использовать `config_generation_id` как replacement для `metadata_hash` или `config_version`.
- Не менять compatibility matching semantics в этом change.

## Decision 1: Источник истины для `config_generation_id` только Designer
`config_generation_id` в рамках change берётся только через существующий Designer execution path командой `GetConfigGenerationID`.

Система не должна:
- вычислять это значение из `$metadata`/OData headers;
- читать его из `Database.version`;
- подменять его данными из RAS;
- требовать extension-specific HTTP endpoint.

Это сохраняет change узким и опирается на уже существующую platform capability.

## Decision 2: `config_generation_id` не является частью canonical shared snapshot identity
Canonical shared snapshot identity остаётся configuration-scoped и продолжает опираться на:
- `config_name`;
- `config_version`;
- `extensions_fingerprint`;
- `metadata_hash`.

`config_generation_id` вводится как отдельный database-scoped provenance marker, резолвимый для конкретной выбранной ИБ в read/refresh path.

Причина: shared snapshot описывает canonical normalized OData surface, тогда как generation id в этом change мы снимаем через конкретную ИБ как probe source. Не нужно в одном change приписывать этому marker'у semantics stronger than proven.

## Decision 3: Persist/read path хранит marker отдельно от `config_version`
Read-model и decision metadata context должны хранить:
- `config_version` как отдельное optional display field;
- `config_generation_id` как отдельный technical marker.

UI должен показывать их раздельно. Пустой `config_version` не должен приводить к потере уже resolved `config_generation_id`.

## Decision 4: Отказ probe не блокирует existing metadata snapshot path, но и не даёт synthetic fallback
Так как change additive и не меняет matching semantics, failure/absence Designer probe не должен ломать существующий metadata snapshot path.

Но при этом система не должна:
- синтетически копировать `config_version` в `config_generation_id`;
- подставлять произвольный fallback из другого runtime source;
- маркировать пустое значение как успешно resolved.

Практический эффект:
- legacy snapshots и snapshots без успешного probe могут возвращать пустой `config_generation_id`;
- после refresh/probe marker появляется без изменения canonical snapshot identity.

## Decision 5: Decision provenance использует marker как auditable enrichment
При публикации decision revision resolved metadata context должен сохранять `config_generation_id`, если он был получен для выбранной ИБ.

Этот marker нужен для:
- operator/analyst diagnostics в `/decisions`;
- audit/read-model;
- будущего ужесточения compatibility semantics отдельным change, если это понадобится.

В этом change compatibility checks не переводятся на `config_generation_id`.

## Risks / Trade-offs
- Плюс: решаем текущую проблему пустого `Config version` технически корректным marker'ом, не выдумывая бизнес-версию.
- Плюс: не нужен extension и не нужен новый runtime surface.
- Плюс: не ломается shared snapshot reuse model.
- Минус: `config_generation_id` не заменяет человекочитаемую версию конфигурации.
- Минус: Designer probe добавляет дополнительный шаг и потенциальную latency/availability зависимость.
- Минус: часть старых snapshot'ов останется без marker до refresh.

## Migration / Rollout
1. Расширить contracts/read-model nullable полем `config_generation_id`.
2. Добавить Designer probe в metadata refresh path.
3. Прокинуть marker в `/decisions` и decision metadata context.
4. Обновить UI `/decisions` на отдельное отображение `Config generation ID`.
5. Старые snapshot'ы не backfill'ятся офлайн в рамках change; поле заполняется по мере refresh/probe.
