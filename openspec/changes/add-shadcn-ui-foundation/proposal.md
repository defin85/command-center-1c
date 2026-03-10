# Change: Поэтапное внедрение `shadcn/ui` как локального UI foundation

## Why
Текущий frontend уже глубоко завязан на `Ant Design`: значимая часть экранов, таблиц, форм, модалок и служебных layout-компонентов использует прямые импорты `antd` и `@ant-design/icons`.

Полный rewrite UI-платформы в один шаг для этого репозитория слишком дорог и рискован: он затронет routing shell, CRUD-heavy backoffice screens, тесты, accessibility и bundle behavior одновременно.

При этом команде нужен задел на будущее, чтобы:
- перестать усиливать vendor lock-in на уровне новых экранов;
- получить project-owned слой UI-примитивов, который можно кастомизировать под собственный design system;
- мигрировать выборочно, а не через big-bang rewrite.

Нужно зафиксировать отдельный change, который задаёт архитектурный контракт для постепенного внедрения `shadcn/ui` в существующий Vite/React frontend без требования немедленно переписать все текущие поверхности.

## What Changes
- Добавить новую capability `ui-component-foundation`.
- Зафиксировать phased coexistence contract между текущими `Ant Design` поверхностями и новым project-owned UI layer на базе `shadcn/ui`.
- Зафиксировать, что будущая миграция идёт по vertical slices и readiness gates, а не через одномоментный rewrite всего frontend.
- Зафиксировать, что новые или целенаправленно переписываемые поверхности должны опираться на локальные UI primitives, а не на прямые vendor imports как primary path.
- Зафиксировать центральный слой design tokens/layout primitives, чтобы mixed-mode migration не приводила к произвольному визуальному дрейфу.

## Impact
- Affected specs:
  - `ui-component-foundation` (new)
- Affected code (expected, when implementing this change):
  - `frontend/package.json` и frontend build tooling
  - `frontend/src/components/ui/**`
  - `frontend/src/lib/ui/**` или эквивалентный слой design tokens/theme helpers
  - выбранные pilot screens / shared layout primitives
  - frontend docs / migration playbook

## Non-Goals
- Немедленный полный rewrite текущего frontend c `Ant Design` на `shadcn/ui`.
- Одновременная миграция CRUD-heavy экранов (`tables/forms/drawers/modals`) без заранее определённых parity criteria.
- Замена существующего routing shell, auth flow и page map в рамках одного стартового change.
- Изменение backend API, OpenAPI contracts или бизнес-поведения системы.

## Assumptions
- `Ant Design` остаётся допустимым runtime dependency на переходный период.
- `shadcn/ui` внедряется как open-code foundation внутри репозитория, а не как внешний “чёрный ящик”.
- Первые migration candidates будут выбраны среди low-risk или isolated UI surfaces, а не среди самых сложных backoffice страниц.
