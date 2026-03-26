## Контекст
Проект уже зафиксировал `WorkspacePage`, `MasterDetailShell`, `EntityList`, `EntityTable`, `EntityDetails` и browser-level mobile fallback как canonical UI platform contract. Но текущая governance почти не различает:
- корректный `master-detail`, где master pane служит выбору сущности;
- и route, где в master pane помещена почти вся полноценная таблица с фильтрами, множеством колонок и горизонтальным скроллом.

Это особенно заметно на:
- `/operations`
- `/databases`
- `/pools/topology-templates`

## Цели
- Сделать `master-detail` визуально и структурно однозначным: master pane отвечает за выбор, detail pane за inspection/action depth.
- Ввести lint-правила для statically checkable anti-patterns, а всё, что плохо формализуется, закрепить browser-level regression tests.
- Сохранить существующий platform layer и refactor сделать через минимальные эволюционные изменения, а не через новую design system или полный rewrite table toolkit.

## Не-цели
- Не переписывать весь frontend на новый визуальный стиль.
- Не пересматривать все authenticated routes сразу.
- Не вводить вторую primary design system или тяжёлую page-builder abstraction.

## Наблюдаемые architectural gaps
1. `MasterDetailShell` задаёт только layout breakpoint, но не semantic contract для master pane.
2. `EntityTable` легально даёт `overflowX: auto` и `scroll.x = max-content`, поэтому его легко использовать как primary master pane, хотя это противоречит роли master column.
3. Текущие lint-правила ловят raw `antd` containers, но не misuse platform primitives.
4. Browser tests уже проверяют narrow viewport fallback, но мало проверяют desktop master-pane discipline и misleading inspect states.

## Решение
### 1. Явный contract для master pane
Master pane в governed `MasterDetail` routes должен оставаться compact selection surface:
- 1-3 ключевых атрибута на row/card;
- явный selected state;
- без зависимости от horizontal overflow как штатного desktop path;
- без превращения в mini data grid с широкой матрицей operational columns.

`EntityTable` остаётся допустимым platform primitive, но не как default master-pane foundation на этих governed routes. Для master pane route должен использовать:
- `EntityList`, или
- компактный platform-owned list primitive/variant, если существующего `EntityList` недостаточно.

### 2. Разделение enforceable invariants
Что должен ловить lint:
- использование `EntityTable`, raw `Table` или `TableToolkit` как primary master pane content на выбранных governed routes;
- master-pane composition, требующую wide horizontal scroll по design;
- возвращение route-level bespoke containers вместо canonical workspace/list/detail pattern.

Что должно оставаться browser-level:
- отсутствие page-wide и pane-wide overflow на canonical scenarios;
- правильное открытие detail на narrow viewport;
- отсутствие misleading completion UI для zero-task/empty inspect states;
- сохранение route-state и selected context.

### 3. Route-specific refactor direction
#### `/operations`
- master pane: compact operation list, filters, selected state;
- detail pane: inspect/timeline/telemetry;
- zero-task execution не должен выглядеть как completed progress bar.

#### `/databases`
- master pane: compact database selection catalog с ключевой идентичностью и health/status summary;
- bulk controls и wide operational density не должны превращать master pane в full-width grid;
- detail pane остаётся owner-ом management contexts.

#### `/pools/topology-templates`
- master pane: compact template catalog;
- detail pane: revision lineage, nodes/edges summary, authoring entry points;
- instructional copy остаётся, но не должна доминировать над catalog/detail workspace.

## Альтернативы
### Оставить это только на визуальный review
Отклонено: structural regressions типа table-first master pane воспроизводимы и должны ловиться автоматически.

### Решать всё только browser-тестами
Отклонено: browser tests слишком дорогие для базовых structural anti-patterns, которые можно поймать линтером.

### Ввести новый большой platform shell специально для master-detail
Не рекомендуется. Это расширяет scope и не нужно для закрытия текущей проблемы. Лучше усилить текущий `MasterDetailShell` contract и route-specific governance.

## Rollout
1. Зафиксировать spec-level contract для master pane и governance.
2. Ввести lint rules и unit tests для lint plugin.
3. Перевести три route на compact master pane.
4. Добить browser regression coverage и validation gate.

## Риски
- Слишком жёсткое lint-правило может зацепить legitimate detail tables. Нужна привязка именно к master-pane composition на targeted routes.
- Если route-specific refactor не разведёт responsibility между pane-ами, можно получить cosmetic rewrite без реального улучшения UX.
- Если оставить `EntityTable` как молчаливо допустимый master-pane path, change не решит корневую причину.
