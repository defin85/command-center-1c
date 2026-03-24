## Контекст
В текущем decision lifecycle уже есть:
- net-new create;
- revise существующей revision;
- guided rollover под другой target metadata context.

Все существующие guided flows вокруг source revision сейчас ведут к publish новой revision того же decision resource через `parent_version_id`.

Пользовательский сценарий clone отличается по доменной семантике:
- source revision нужна только как удобный seed;
- resulting artifact должен стать новым independent decision resource;
- дальнейшая эволюция clone не должна продолжать lineage исходного `decision_table_id`.

При этом отдельный backend primitive для clone не нужен. Existing create path уже создаёт независимый resource, если payload содержит новый `decision_table_id` и не содержит `parent_version_id`.

## Цели
- Дать аналитику явный и discoverable clone action в `/decisions`.
- Не смешивать clone semantics с rollover semantics.
- Переиспользовать existing create/publish contract без нового backend lifecycle.
- Сохранить metadata-aware validation против выбранной target database.

## Не-цели
- Не менять runtime/binding semantics pinned decision revisions.
- Не добавлять автоматический rebind consumers.
- Не расширять active transfer workbench change.
- Не вводить hidden fallback, который молча превращает clone в revise или rollover.

## Решения

### Decision 1: Clone — это отдельный editor mode, а не вариация rollover
`rollover` и `clone` решают разные задачи:
- `rollover` публикует новую revision того же `decision_table_id` и сохраняет lineage через `parent_version_id`;
- `clone` публикует новый `decision_table_id` и НЕ передаёт `parent_version_id`.

Поэтому UI должен показывать отдельный action и отдельный explanatory copy, а не перегружать существующий rollover modal ещё одной скрытой развилкой.

### Decision 2: Clone переиспользует create payload, а source revision выступает только seed
Clone mode открывает editor с копией source policy, name и description. При publish:
- `decision_table_id` обязан быть editable и уникальным;
- `parent_version_id` не отправляется;
- `database_id` продолжает резолвить target metadata context так же, как в обычном create flow.

Это сохраняет простой backend contract и не требует отдельного endpoint.

### Decision 3: Metadata contract clone совпадает с обычным create
Clone не должен обходить metadata-aware validation только потому, что source revision уже существовала.

Если аналитик выбрал target database:
- clone валидируется против resolved metadata snapshot этой базы;
- resulting revision получает target metadata provenance текущего create flow;
- incompatibility/missing fields fail-closed так же, как в обычном create или rollover.

### Decision 4: Clone не меняет existing consumers
Publish clone:
- не перепривязывает workflow definitions;
- не перепривязывает binding profiles или pool bindings;
- не влияет на runtime projections существующих pins.

UI copy должен проговаривать это так же явно, как rollover copy сейчас проговаривает отсутствие auto-rebind.

## Риски и компромиссы
- Аналитик может спутать clone и rollover, если copy/CTA будут слишком похожи. Поэтому title, help text и submit label должны жёстко различать semantics.
- При clone в другой metadata context publish может fail-closed на target validation. Это ожидаемо и должно объясняться как normal create semantics, а не как баг clone flow.
- Поскольку clone не использует `parent_version_id`, resulting detail не будет частью revision chain исходного decision resource. Это и есть целевая продуктовая семантика.

## План реализации
1. Обновить spec `/decisions` и `document_policy` lifecycle, добавив explicit clone semantics.
2. Добавить новый editor mode `clone` в frontend state/copy/helpers.
3. Показать action `Clone selected revision` только для поддерживаемых `document_policy` revisions.
4. Переиспользовать existing create save path без `parent_version_id`.
5. Добавить regression tests на mode/copy/payload.
