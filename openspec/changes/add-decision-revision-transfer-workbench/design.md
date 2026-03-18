## Контекст
`/decisions` уже поддерживает guided rollover: source revision может использоваться как seed для publish новой revision под target database, а resulting revision получает новый metadata context. Этого достаточно для базового lifecycle contract, но недостаточно для аналитического UX, где нужно быстро переносить близкие по смыслу document policies между соседними configuration profile / release context.

Проблема здесь не в runtime model. Runtime уже закреплён вокруг concrete `decision_revision`, pinned workflow/binding refs и deterministic materialization в `document_policy.v1`. Проблема в authoring ergonomics: аналитику нужен явный экран переноса, который показывает, какие source mappings уже подходят target context, а какие требуют ручного remap.

Важно: этот change НЕ стартует с нуля. Он должен расширять уже доставленный guided rollover baseline, а не вводить второй параллельный authoring lifecycle поверх тех же самых concrete revisions.

## Цели
- Дать аналитику discoverable transfer flow для concrete `decision_revision`.
- Сохранить текущую runtime модель: concrete revisions, pinned consumers, deterministic compile и auditable provenance.
- Явно отделить default ready-to-pin selection от source-only transfer mode.
- Зафиксировать fail-closed remap semantics против target metadata snapshot.
- Повысить точность automatic remap через stable metadata identity там, где она доступна.

## Не-цели
- Не вводить abstract `Decision revision`, `Decision blueprint` или другой новый runtime artifact.
- Не делать `/decisions` primary surface для управления configuration profile или metadata snapshot; canonical maintenance остаётся в `/databases`.
- Не добавлять автоматическую массовую перепривязку workflow definitions, workflow bindings или runtime projections на новую revision.
- Не обещать fully automatic semantic transfer между разными document archetypes без подтверждения аналитика.
- Не требовать, чтобы standard OData interface сам возвращал stable design-time metadata IDs для этого change.

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

### Decision 3: Metadata identity для transfer matching использует design-time IDs как primary signal
Для remap между source policy и target metadata snapshot change использует двухуровневую стратегию identity:
- primary signal — stable design-time metadata identifiers из `ConfigDumpInfo.xml`/`ibcmd`-enriched snapshot;
- fallback signal — canonical metadata path/name + type/shape, если design-time IDs недоступны.

Практически это означает:
- standard OData interface остаётся source-of-truth для published metadata surface и runtime shape;
- `ConfigDumpInfo.xml`/XML configuration dump используется как source-of-truth для design-time metadata identity;
- если target/source item не имеет доступного design-time ID, backend не пытается «додумать» exact match только по display name;
- если fallback по canonical path/name + type/shape даёт больше одного правдоподобного target candidate, item классифицируется как `ambiguous`, а не как `matched`.

Это удерживает change в совместимых границах:
- transfer workbench может становиться точнее там, где доступен `ibcmd`/config dump;
- OData-only среды не блокируются, но получают более консервативный report;
- standard attributes/platform-defined fields допускают explicit fallback по canonical tokens, когда design-time ID неэкспортируем или недоступен.

### Decision 4: Transfer report становится явной частью authoring contract
Transfer workbench ДОЛЖЕН явно классифицировать элементы source policy относительно target snapshot:
- `matched` — автоматически переносится без ручного вмешательства;
- `ambiguous` — найдено несколько правдоподобных target matches;
- `missing` — target reference не найден;
- `incompatible` — тип/shape target metadata не допускает прямой перенос.

Publish новой revision блокируется fail-closed, пока остаются `ambiguous`, `missing` или `incompatible` элементы.

### Decision 5: Transfer использует stateless two-phase contract: server-evaluated preview + publish через existing revision publish core
MVP transfer workbench фиксируется как два явных шага:
- `transfer preview` принимает source revision и target database, резолвит target context на backend и возвращает transfer report/read-model для analyst UX;
- `transfer publish` принимает результат analyst remap, повторно считает report относительно текущего target snapshot и только после этого создаёт новую revision;
- существующий core publish/create revision переиспользуется как финальный шаг materialization новой concrete revision.

MVP НЕ вводит persistent draft artifact, отдельную abstract revision или скрытый stateful transfer session.

Это снимает двусмысленность между UX workbench и backend contract:
- preview считается авторитативно на server side, а не в браузере;
- publish не доверяет устаревшему client-side report и повторно валидирует unresolved items;
- existing create/revise/rollover lifecycle для обычного `/decisions` остаётся совместимым и не перегружается transfer-only semantics;
- если implementation сможет безопасно переиспользовать существующий rollover publish без отдельного `transfer publish` endpoint, это считается предпочтительным минимальным вариантом.

### Decision 6: Publish создаёт только новую concrete revision и не меняет existing consumers
Transfer workbench не получает отдельный runtime artifact и не меняет semantics existing pins. Успешный publish:
- использует `parent_version_id` source revision;
- валидирует финальный policy против target snapshot;
- сохраняет target metadata provenance в новой revision;
- не перепривязывает workflow definitions, bindings и runtime projections автоматически.

### Decision 7: Default compatible selection и source-selection остаются разными режимами
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
- `ConfigDumpInfo.xml` IDs полезны как technical identity signal, но platform docs рассматривают их как internal identifiers; значит change должен использовать их для matching/audit, а не как analyst-facing public contract.
- В OData-only среде без `ibcmd`/config dump quality auto-remap будет ниже, поэтому `ambiguous` cases станут встречаться чаще; это ожидаемый fail-closed trade-off.

## План миграции
1. Зафиксировать spec-level transfer contract поверх уже shipped guided rollover semantics.
2. Зафиксировать metadata identity contract: `ConfigDumpInfo.xml`/`ibcmd`-enriched design-time IDs как primary signal и canonical path/name + type/shape как fallback.
3. Определить stateless two-phase API/read-model shape: `transfer preview` и `transfer publish`.
4. Реализовать backend remap/validation path поверх существующей publish semantics, сохранив existing revision publish core как финальный шаг materialization.
5. Расширить existing rollover UI source/target summary до transfer report и guided remap вместо отдельного параллельного editor lifecycle.
6. Добавить analyst-facing tests fail-closed поведения.

## Открытые вопросы
- Нужен ли отдельный "fast publish" UX для полностью `matched` transfer report, или достаточно общего publish flow?
- Нужно ли в следующем change выделять library/preset слой для часто повторяющихся "схематозов", или transfer workbench закроет основной аналитический сценарий?
