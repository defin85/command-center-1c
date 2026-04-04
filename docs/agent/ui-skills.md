# UI Skill Workflow

Статус: authoritative agent-facing guidance.

Этот документ фиксирует policy для активного использования shared UI skills из user-level каталога `/home/egor/.agents/skills/` в `command-center-1c`. Если frontend/UI-задача явно совпадает с профилем скилла, агент должен использовать его без отдельного запроса пользователя.

## Где лежат UI Skills

- Shared UI skills: `/home/egor/.agents/skills/<skill>/SKILL.md`
- Repo-local runtime helpers: `.agents/skills/runtime-debug/SKILL.md`

Для UI-задач shared skills являются primary routing layer, а repo-local `runtime-debug` подключается дополнительно, когда нужна проверка живого runtime, restart или eval.

## Правило По Умолчанию

- Не ждать явной команды вида "используй `frontend-design`" или "подключи `dogfood`".
- Выбирать минимальный набор shared UI skills, который реально нужен задаче.
- Не подключать skill ради ритуала: узкая локальная правка не должна тянуть audit-chain целиком.
- Если пользователь явно назвал skill, это важнее default routing.
- UI skills не заменяют обязательный verification workflow из [VERIFY.md](./VERIFY.md).

## Матрица Выбора

- Визуальный/UX review без кодинга: `critique`
- Живой браузерный прогон, exploratory QA, bug hunt: `dogfood`
- Новый UI, заметный редизайн, новая route-page или крупная page composition: `frontend-design`
- Экран должен лучше следовать platform primitives и существующей системе: `normalize`
- Нужна адаптация под desktop/mobile/narrow viewport: `adapt`
- Нужно закрыть overflow, empty states, validation, i18n, error handling, edge cases: `harden`
- Нужен финальный проход по spacing, hierarchy и consistency: `polish`
- Нужен системный standards pass по accessibility/performance/theme/responsive: `audit`
- Нужна более строгая web-guidelines проверка: `web-design-guidelines`
- Интерфейс слишком шумный или перегруженный: `quieter`, `distill`
- Интерфейс слишком безопасный, без характера или недостаточно выразительный: `bolder`, `colorize`, `delight`
- Нужны motion/micro-interactions: `animate`
- Нужна доработка copy, labels, helper text, error text: `clarify`
- Нужно извлечь переиспользуемые UI-паттерны или design-layer primitives: `extract`
- Нужно улучшить onboarding, empty state или first-run flow: `onboard`
- Нужно улучшить rendering/perf path интерфейса: `optimize`

## Рекомендуемые Последовательности

### UX Review

- `critique`
- `dogfood`, если нужен живой сценарий
- `audit`, если change крупный или высокорисковый

### Новый UI Или Крупный Redesign

- `frontend-design`
- `adapt`
- `harden`
- `polish`

Если уже есть спорный текущий экран, добавь `critique` перед имплементацией.

### Platform Migration Или Page Composition Cleanup

- `normalize`
- `adapt`
- `harden`
- `polish`

### Перед Ship

- `dogfood`
- `harden`
- `polish`
- `audit`, если surface operator-facing и change широкий

## Связь С Runtime И Verification

- Для живой проверки UI с поднятыми runtime при необходимости добавляй repo-local `runtime-debug`.
- Для frontend work после skill-routing используй минимальный релевантный gate из [VERIFY.md](./VERIFY.md):
  - `cd frontend && npm run lint`
  - `cd frontend && npm run test:run -- <path>`
  - `cd frontend && npm run test:browser:ui-platform`
  - `cd frontend && npm run validate:ui-platform`
- Для governed platform migrations default blocking gate остаётся тем же: `lint`, `test:run`, `test:browser:ui-platform`, затем production build.

## Что Не Делать

- Не считать выбор skill-ов заменой тестам и browser gates.
- Не подключать сразу весь UI skill catalog без признаков, что задача этого требует.
- Не обходить root `UI Platform Contract` из [AGENTS.md](../../AGENTS.md) только потому, что конкретный skill предлагает более широкий дизайн-манёвр.
