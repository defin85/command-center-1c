## Контекст
Обе страницы уже соответствуют platform governance на уровне layout foundation, но по текущему UX всё ещё ощущаются как "внутренняя инженерная поверхность", а не как чистый операторский workspace.

Подтверждённые текущие проблемы:
- tenant selector в shared shell не имеет устойчивого accessible name: `frontend/src/components/layout/MainLayout.tsx`;
- `/decisions` хранит `selectedDatabaseId`, `selectedDecisionId` и `snapshotFilterMode` только в local state: `frontend/src/pages/Decisions/useDecisionsCatalog.ts`;
- `/decisions` использует interactive `div role="button"` для выбора revision и показывает шесть почти равноправных действий в одном action strip: `frontend/src/pages/Decisions/DecisionCatalogPanel.tsx`, `frontend/src/pages/Decisions/DecisionsPage.tsx`;
- `/pools/binding-profiles` хранит `search`, `selectedProfileId`, drawer state только в local state и использует row-click-only selection: `frontend/src/pages/Pools/PoolBindingProfilesPage.tsx`;
- `/pools/binding-profiles` выводит opaque pins и raw JSON слишком рано, до operator-facing summary и next-step контекста.

Проблема здесь не в отсутствии компонентов. Проблема в contract-level ergonomics:
- состояние нельзя адресовать и шарить;
- primary selection читается слабее, чем должен читать master-detail workspace;
- route copy и detail hierarchy перегружены внутренними терминами и diagnostics.

## Цели
- Сделать `/decisions` и `/pools/binding-profiles` shareable stateful workspaces с устойчивым deep-link/back-forward path.
- Привести primary selection и critical controls к keyboard-first, semantic и accessible поведению.
- Упростить visual/task hierarchy так, чтобы первый экран объяснял основное действие, а не всю внутреннюю модель платформы.
- Оставить diagnostics/raw payload доступными, но не доминирующими на default path.

## Не-цели
- Не вводить новый backend contract.
- Не переписывать весь `MainLayout` или весь набор platform primitives ради двух маршрутов.
- Не проводить большой visual redesign с новыми токенами, темой или новым shell layout.
- Не превращать change в broad “UX cleanup across repo”.

## Решения

### Decision 1: URL становится частью usability contract для stateful workspace routes
Для `/decisions` и `/pools/binding-profiles` primary route context должен жить в query params.

Минимальный обязательный набор:
- `/decisions`: `database`, `decision`, `snapshot`;
- `/pools/binding-profiles`: `q`, `profile`, `detail`.

Почему так:
- deep-link и back/forward являются частью operator efficiency, а не optional enhancement;
- это решает самый дорогой usability gap без изменения backend;
- это лучше соответствует admin/backoffice nature этих страниц.

Компромисс:
- change НЕ требует создавать общий route-state framework для всего frontend;
- сначала предпочтителен локальный, понятный implementation per route;
- общий helper допустим только если дублирование между двумя страницами становится явным и небольшим.

### Decision 2: Primary selection должна быть semantic и явно выделенной
Для обеих страниц selection больше не должна опираться только на row click или generic `div role="button"`.

Целевой паттерн:
- явный semantic trigger (`button`, `link`, selection control в таблице или другой platform-consistent affordance);
- программный selected state (`aria-selected`, `aria-current` или эквивалентный семантически корректный путь);
- более сильный visual selected state, чем одна тонкая левая полоска.

Это не требует полной замены `EntityList`/`EntityTable`. Change может идти route-local, а platform primitive трогать только если одинаковый affordance нужен обеим страницам без лишнего усложнения.

### Decision 3: `/decisions` должен стать task-first authoring workspace
На `/decisions` основной путь должен считываться сразу:
- выбрать контекст базы;
- открыть существующую revision или создать новую policy;
- при необходимости перейти к revise/rollover;
- advanced import/legacy/raw flows остаются доступными, но перестают конкурировать с основным authoring path.

Следствия:
- `New policy` остаётся единственным явным primary CTA;
- import и diagnostic-heavy controls группируются как secondary actions;
- metadata diagnostics, provenance и raw/advanced context прячутся за явным раскрытием;
- copy говорит языком задачи, а не перечисляет всю внутреннюю топологию платформы.

### Decision 4: `/pools/binding-profiles` должен быть summary-first, а не inspect-first
Первый экран detail pane должен отвечать на три вопроса:
- что это за профиль;
- на какой workflow/revision он опирается;
- что оператор может сделать дальше.

Следствия:
- summary и action area поднимаются выше;
- usage и revision history остаются важными, но идут после summary;
- opaque revision ids, workflow pins и raw JSON не исчезают, но становятся advanced/disclosure layer;
- search и selection получают устойчивые labels и URL-addressable state.

### Decision 5: Shared shell labels входят в границу change, но только там, где они влияют на эти маршруты
Tenant selector в `MainLayout` используется на обоих маршрутах и сейчас ломает accessibility/usability baseline. Поэтому он входит в scope change.

При этом change НЕ расширяется на весь shell audit:
- достаточно закрыть persistent accessible naming и не запускать большой cleanup остальных header controls.

## Порядок внедрения и целевые файлы

### Шаг 1: Shared baseline
- `frontend/src/components/layout/MainLayout.tsx`
- route-level/browser tests, проверяющие persistent labels

Сначала закрываются label/accessibility gaps, чтобы subsequent route tests опирались на корректный shell baseline.

### Шаг 2: URL-state и selection contract
- `frontend/src/pages/Decisions/useDecisionsCatalog.ts`
- `frontend/src/pages/Decisions/DecisionCatalogPanel.tsx`
- `frontend/src/pages/Pools/PoolBindingProfilesPage.tsx`
- при необходимости небольшой shared helper в route-local/frontend utility слое

Сначала фиксируется адресуемость состояния и semantic selection, потому что без этого дальнейшая визуальная переработка останется косметической.

### Шаг 3: `/decisions` hierarchy и copy
- `frontend/src/pages/Decisions/DecisionsPage.tsx`
- `frontend/src/pages/Decisions/DecisionDetailPanel.tsx`
- связанные route tests/browser smoke

После стабилизации state/navigation перерабатываются action hierarchy, copy и progressive disclosure.

### Шаг 4: `/pools/binding-profiles` summary-first detail
- `frontend/src/pages/Pools/PoolBindingProfilesPage.tsx`
- связанные route tests/browser smoke

На этом шаге detail pane переупорядочивается так, чтобы operator summary и next actions шли до opaque diagnostics.

## Alternatives considered

### Alternative A: Ограничиться только accessibility fixes
Отклонено:
- labels и keyboard fixes важны, но не решают deep-link/back-forward и weak task hierarchy;
- пользователь всё равно будет терять контекст и работать через громоздкий detail flow.

### Alternative B: Сразу сделать общий workspace state framework для всего frontend
Отклонено:
- слишком большой scope для локальной usability задачи;
- повышает риск архитектурной работы ради двух маршрутов;
- не соответствует guardrail "favor straightforward, minimal implementations first".

### Alternative C: Решить только copy и визуальную иерархию
Отклонено:
- без URL-state и semantic selection это будет cosmetic improvement, а не полноценная usability remediation.

## Риски и компромиссы
- URL-state может затронуть существующие tests и browser smoke, потому что route mounting/selection перестанет быть purely local.
- Если `add-decision-revision-transfer-workbench` начнёт реализовываться параллельно, надо удержать один action hierarchy contract для `/decisions`, а не добавлять ещё один competing primary flow.
- Перенос raw JSON в advanced disclosure нельзя делать так, чтобы operator потерял доступ к diagnostic truth; disclosure должен быть discoverable и стабильным.
