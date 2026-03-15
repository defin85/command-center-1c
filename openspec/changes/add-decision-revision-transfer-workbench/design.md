## Контекст
`/decisions` уже поддерживает guided rollover: source revision может использоваться как seed для publish новой revision под target database, а resulting revision получает новый metadata context. Этого достаточно для базового lifecycle contract, но недостаточно для аналитического UX, где нужно быстро переносить близкие по смыслу document policies между соседними configuration profile / release context.

Проблема здесь не в runtime model. Runtime уже закреплён вокруг concrete `decision_revision`, pinned workflow/binding refs и deterministic materialization в `document_policy.v1`. Проблема в authoring ergonomics: аналитику нужен явный экран переноса, который показывает, какие source mappings уже подходят target context, а какие требуют ручного remap.

## Цели
- Дать аналитику discoverable transfer flow для concrete `decision_revision`.
- Сохранить текущую runtime модель: concrete revisions, pinned consumers, deterministic compile и auditable provenance.
- Явно отделить default ready-to-pin selection от source-only transfer mode.
- Зафиксировать fail-closed remap semantics против target metadata snapshot.

## Не-цели
- Не вводить abstract `Decision revision`, `Decision blueprint` или другой новый runtime artifact.
- Не делать `/decisions` primary surface для управления configuration profile или metadata snapshot; canonical maintenance остаётся в `/databases`.
- Не добавлять автоматическую массовую перепривязку workflow definitions, workflow bindings или runtime projections на новую revision.
- Не обещать fully automatic semantic transfer между разными document archetypes без подтверждения аналитика.

## Решения

### Decision 1: Transfer строится вокруг concrete source revision, а не вокруг новой абстрактной сущности
Source revision остаётся единственным reusable seed. Она:
- не мутируется;
- не становится late-bound artifact;
- используется только как authoring template для новой concrete revision.

Это сохраняет совместимость с текущими инвариантами:
- binding pin-ит concrete revision;
- preview/compile работают с concrete `document_policy.v1`;
- provenance сохраняется в resulting revision, а не вычисляется постфактум.

### Decision 2: Target context по-прежнему выбирается через database, а `/decisions` показывает resolved profile/snapshot
Для MVP transfer workbench не вводит отдельный mutate surface по `Configuration profile`. Аналитик выбирает target database, а `/decisions` показывает:
- target database;
- resolved `configuration profile`;
- resolved target `metadata snapshot`;
- source revision provenance.

Это удерживает границу ответственности:
- `/databases` управляет profile/snapshot;
- `/decisions` потребляет их как authoring context.

### Decision 3: Transfer report становится явной частью authoring contract
Transfer workbench ДОЛЖЕН явно классифицировать элементы source policy относительно target snapshot:
- `matched` — автоматически переносится без ручного вмешательства;
- `ambiguous` — найдено несколько правдоподобных target matches;
- `missing` — target reference не найден;
- `incompatible` — тип/shape target metadata не допускает прямой перенос.

Publish новой revision блокируется fail-closed, пока остаются `ambiguous`, `missing` или `incompatible` элементы.

### Decision 4: Publish создаёт только новую concrete revision и не меняет existing consumers
Transfer workbench не получает отдельный runtime artifact и не меняет semantics existing pins. Успешный publish:
- использует `parent_version_id` source revision;
- валидирует финальный policy против target snapshot;
- сохраняет target metadata provenance в новой revision;
- не перепривязывает workflow definitions, bindings и runtime projections автоматически.

### Decision 5: Default compatible selection и source-selection остаются разными режимами
Revision вне default compatible set может быть полезной как source для transfer, но не должна становиться ready-to-pin candidate автоматически.

Практически это означает:
- default `/decisions` list продолжает показывать compatible concrete revisions;
- diagnostics/source mode разрешает взять revision вне compatible set как template;
- UI явно различает "можно pin-ить сейчас" и "можно использовать как источник переноса".

## Alternatives considered

### Alternative A: Ввести abstract `Decision revision`
Отклонено:
- ломает текущую concrete/pinned модель;
- усложняет lineage и deterministic compile;
- переносит проблему из UX в domain model.

### Alternative B: Ограничиться существующим guided rollover без transfer report
Отклонено:
- у аналитика остаётся low-level revise flow;
- не появляется явного remap/diff surface;
- сложнее безопасно переносить policy между отличающимися metadata context.

### Alternative C: Сразу добавить библиотеку schematose templates/presets
Отложено:
- это отдельный уровень reusable authoring artifacts;
- сначала нужно закрепить перенос между concrete revisions и target metadata context;
- иначе появится второй abstraction layer без ясного publish contract.

## Риски и компромиссы
- Автоматический remap может быть "почти правильным", поэтому ambiguous/missing/incompatible cases нельзя публиковать молча.
- UI `/decisions` станет сложнее, если transfer mode не будет отделён от default ready-to-pin flow.
- Если в будущем понадобится reusable preset library, этот change должен остаться совместимым и не подменять presets скрытой transfer-магией.

## План миграции
1. Зафиксировать spec-level transfer contract поверх текущего rollover semantics.
2. Определить API/read-model shape для source context, target context и transfer report.
3. Реализовать backend remap/validation path поверх существующей publish semantics.
4. Добавить analyst-facing transfer UI и тесты fail-closed поведения.

## Открытые вопросы
- Нужен ли отдельный "fast publish" UX для полностью `matched` transfer report, или достаточно общего publish flow?
- Нужно ли в следующем change выделять library/preset слой для часто повторяющихся "схематозов", или transfer workbench закроет основной аналитический сценарий?
