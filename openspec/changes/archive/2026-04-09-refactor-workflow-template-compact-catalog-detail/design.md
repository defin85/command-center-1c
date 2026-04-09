## Контекст

`/workflows` и `/templates` уже прошли первую platform migration: они используют `MasterDetailShell`, route-backed selected context и canonical detail fallback на narrow viewport. Но их master pane всё ещё устроен как wide table внутри split shell, поэтому итоговый UX остаётся hybrid:
- каталог тяжёлый для быстрого сканирования;
- primary actions размазаны между строкой, header и detail;
- широкие provenance/status columns конкурируют с самой задачей выбора сущности.

При этом в репо уже есть более чистый образец нужного family: `/databases`, где master pane — компактный selection catalog, а detail pane — основной management/inspect workspace.

## Goals

- Привести `/templates` и `/workflows` к одному и тому же compact `catalog-detail` language.
- Сделать master pane scan-friendly и selection-first.
- Сконцентрировать primary actions, provenance и policy framing в detail pane.
- Подготовить эти routes к будущему opt-in presentation layer без сохранения table-heavy debt.

## Non-Goals

- Не переводить эти routes в single-pane `catalog-workspace`.
- Не менять workflow designer, workflow monitor или template backend semantics.
- Не удалять все таблицы из feature area; только убрать их из primary master pane.

## Решения

### 1. Canonical anchor — `/databases`, а не `/artifacts`

`/templates` и `/workflows` остаются `catalog-detail` routes. Значит, их нужно доводить до зрелого split/detail language, а не переводить в другой workspace family.

`/artifacts` остаётся отдельным reference только для secondary surfaces, но не для route-level page model.

### 2. Master pane должен отвечать только за выбор и короткую ориентировку

В master pane допустимы:
- название сущности;
- 1-3 ключевых статуса;
- короткая summary строка;
- понятный selected state;
- локальный search/filter, если он не делает pane data-dense.

В master pane не должны жить:
- wide provenance grids;
- длинные наборы колонок;
- icon-first action strips;
- primary edit/execute flows.

### 3. Detail pane — основной носитель действий и плотности

Для обеих страниц detail pane должен стать местом, где живут:
- inspect summary;
- provenance и execution contract;
- publish/manage actions для templates;
- inspect/edit/clone/execute handoff для workflows;
- diagnostics links и richer metadata blocks.

### 4. `/templates` и `/workflows` нормализуются одинаково, но не идентично

`/templates` должен быть более governance/contract-first:
- publish/access/provenance важнее быстрых row actions;
- detail pane должен объяснять "что именно будет выполнено" и в каком статусе публикации находится template.

`/workflows` должен быть более action-first:
- detail pane должен давать чёткий cluster переходов в authoring/execute/inspect;
- сама library остаётся компактной и не превращается в diagnostics table.

### 5. Table density остаётся допустимой только как secondary surface

`TableToolkit` и wide tabular composition не запрещаются полностью. Они остаются допустимыми:
- внутри detail-owned blocks;
- в dedicated diagnostics/policy subviews;
- в explicit full-width secondary contexts.

Запрещается только их роль как default primary master-pane composition path.

## Alternatives

### A. Оставить текущий hybrid

Отклонено.

Это сохраняет визуальный и поведенческий конфликт с уже принятым compact `catalog-detail` direction и мешает будущим presentation preferences.

### B. Перевести `/templates` и `/workflows` в стиль `/artifacts`

Отклонено.

Это сломает route family и приведёт к смешению `catalog-detail` и `catalog-workspace`, хотя для этих routes уже принят другой contract.

### C. Сначала сделать user preference switch, потом решать layout debt

Отклонено.

Preferences поверх table-heavy hybrid только законсервируют текущую проблему, а не исправят её.

## Риски / Trade-offs

- Можно слишком "обеднить" каталог и спрятать важные сигналы.
  - Mitigation: оставлять в master pane только действительно critical summary/status cues.
- Detail pane может стать перегруженным.
  - Mitigation: группировать информацию по inspect/action/policy sections и уводить вторичную плотность в secondary surfaces.
- `/workflows` может потерять discoverability частых действий, если всё унести слишком глубоко.
  - Mitigation: делать action cluster сразу в верхней части detail pane, а не скрывать его ниже fold.

## Migration Plan

1. Зафиксировать route-level compact catalog truth в specs.
2. Включить `compact-selection` governance expectation для `/templates` и `/workflows`.
3. Нормализовать `/templates`.
4. Нормализовать `/workflows`.
5. Добавить targeted unit/browser coverage.
6. После стабилизации отдельно решать optional presentation preferences для этих routes.
