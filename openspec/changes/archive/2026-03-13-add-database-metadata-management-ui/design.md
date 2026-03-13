## Context
Текущая архитектура уже различает две разные сущности:
- business identity / reuse key снапшота (`config_name + config_version`), который приходит из persisted `business_configuration_profile` и обновляется через async verification path;
- содержимое metadata snapshot (`snapshot_id`, `metadata_hash`, payload, provenance, drift markers), которое обновляется через metadata refresh path.

Но в UI это различие почти не видно:
- `/pools/catalog` прячет `Load metadata` / `Refresh metadata` внутри topology edge builder;
- `/decisions` показывает metadata context, но не даёт ясного canonical handoff на место, где этим context управляют;
- `/databases` уже является per-infobase operational surface для credentials, DBMS metadata, `ibcmd` profile и extensions, но metadata/profile controls там отсутствуют.

## Goals
- Сделать `/databases` каноническим operator-facing местом для управления configuration profile и metadata snapshot конкретной ИБ.
- Явно разделить в UI:
  - identity/reuse key конфигурации;
  - содержимое и состояние metadata snapshot.
- Убрать primary mutate UX для metadata maintenance из consumer surfaces.
- Сохранить текущие backend contracts и минимизировать объём change.

## Non-Goals
- Не менять storage model `business_configuration_profile` или metadata snapshots.
- Не добавлять новый top-level route, если существующего `/databases` достаточно.
- Не переносить `decision` authoring или topology editing в `/databases`.
- Не превращать `/decisions` или `/pools/catalog` в workflow/operations monitor.

## Decisions
### Decision 1: `/databases` становится canonical operational surface
Управление configuration profile и metadata snapshot должно жить рядом с другими per-database controls.

Это делает `/databases` естественным "паспортом ИБ":
- connection/credentials;
- DBMS metadata;
- `ibcmd` connection profile;
- extensions;
- configuration profile / metadata snapshot.

Минимальная реализация должна использовать drawer/panel или аналогичный scoped surface внутри `/databases`, а не новый route.

### Decision 2: UI обязан различать identity и snapshot
В одном surface должны быть явно разделены два блока:
- `Configuration profile / reuse key`
  - `config_name`
  - `config_version`
  - `config_generation_id`
  - verification status / verified at
- `Metadata snapshot`
  - `snapshot_id`
  - `resolution_mode`
  - `metadata_hash`
  - `observed_metadata_hash`
  - `publication_drift`
  - `provenance_database_id`
  - fetched/confirmed timestamps

Пользователь не должен угадывать, какое действие обновляет какой набор полей.

### Decision 3: Mutating actions разделяются по смыслу
В UI должны существовать два разных действия:
- `Re-verify configuration identity`
  - async flow;
  - ведёт через operations/worker path;
  - должен показывать, что речь идёт о business identity конфигурации.
- `Refresh metadata snapshot`
  - отдельный metadata refresh path;
  - обновляет snapshot state и drift diagnostics;
  - не должен маркироваться как identity refresh.

### Decision 4: Consumer surfaces только потребляют и перенаправляют
`/pools/catalog` и `/decisions` должны оставаться metadata-aware consumer surfaces:
- показывать readonly status/context;
- блокировать действия fail-closed, если контекст отсутствует;
- давать явный CTA/handoff в `/databases`.

Они не должны оставаться primary местом, где оператор ищет refresh/reverify controls.

### Decision 5: Existing backend contracts переиспользуются
Этот change не требует новой backend модели.

На первом этапе достаточно переиспользовать:
- existing metadata catalog read/refresh endpoints для snapshot state;
- existing operations/worker execution path для business identity re-verify;
- existing `/databases` permission model.

## Trade-offs
- Плюс: operator UX становится предсказуемым, потому что per-database operational actions собраны в одном месте.
- Плюс: consumer screens перестают смешивать authoring и metadata maintenance.
- Плюс: change можно реализовать как frontend/IA refinement без пересборки runtime semantics.
- Минус: в `/databases` станет больше controls, поэтому нужен аккуратный panel/drawer вместо перегруженной таблицы.
- Минус: придётся обновить тексты блокирующих ошибок и CTA на нескольких страницах.

## Migration Plan
1. Ввести новый capability для `/databases` metadata management surface.
2. Зафиксировать handoff contract для `/pools/catalog`.
3. Зафиксировать handoff contract для `/decisions`.
4. При реализации обновить frontend tests, чтобы доказать отсутствие hidden primary mutate path в consumer surfaces.

## Open Questions
- Нужно ли на первом этапе показывать в `/databases` inline history последних re-verify/refresh запусков, или достаточно current state + link в `/operations`?
- Нужно ли сохранять в `/pools/catalog` read-only badge текущего metadata catalog для builder convenience, если canonical mutate actions уже перенесены в `/databases`?
