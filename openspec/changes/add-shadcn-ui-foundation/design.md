## Context
Текущий frontend построен на `React 18 + TypeScript + Vite + React Router + Ant Design`. По состоянию на момент создания change, прямые импорты `antd`/`@ant-design/icons` присутствуют в большом числе frontend файлов, что делает полный “switch” UI foundation дорогим по коду, тестам и UX-рискам.

`shadcn/ui` подходит как open-code foundation для project-owned design system, но не является drop-in replacement для всего объёма текущего backoffice-heavy UI.

Поэтому для этого репозитория нужен не big-bang rewrite, а staged migration contract.

## Goals
- Подготовить архитектурную основу для постепенного внедрения `shadcn/ui`.
- Уменьшить зависимость новых экранов от прямых vendor imports.
- Ввести локальный слой UI primitives и theme/tokens, контролируемый самим проектом.
- Сохранить возможность shipping без обязательной массовой миграции существующих экранов.

## Non-Goals
- Не переписывать весь frontend в рамках одного change.
- Не обещать parity для всех `Ant Design` сценариев до pilot validation.
- Не делать одновременно redesign всех существующих страниц.

## Constraints
- В проекте уже есть много сложных backoffice screens с таблицами, формами, modal/drawer flows и плотной информационной архитектурой.
- Нельзя ломать текущие auth guards, route map, app shell и существующие test suites ради самой миграции UI foundation.
- Mixed-mode период неизбежен: некоторое время `Ant Design` и новый local UI layer будут сосуществовать.

## Decision
Принять phased strategy:

1. Не удалять `Ant Design` на первом этапе.
2. Подключить `shadcn/ui` и связанные стили как дополнительный foundation layer.
3. Все новые или целенаправленно переписываемые поверхности вести через локальный project-owned UI layer.
4. Сложные admin-heavy surfaces оставлять на `Ant Design`, пока не появится подтверждённая parity по поведению и DX.
5. Мигрировать не по типу “все кнопки/все модалки”, а по vertical slices.

## Architectural Shape
Предполагаемая структура будущей реализации:

- `frontend/src/components/ui/**`
  - project-owned primitives и composed controls
- `frontend/src/lib/ui/**`
  - theme helpers, tokens, class utilities, adapter helpers
- feature/page code
  - потребляет локальные primitives
  - не использует `shadcn/ui` raw components как primary import path

## Migration Tiers
Рекомендуемые tiers:

- Tier 1: low-risk / isolated surfaces
  - empty states
  - detail cards
  - simple dialogs
  - secondary dashboards / informational pages
- Tier 2: medium-complexity surfaces
  - multi-section forms без тяжёлых table interactions
  - editors с ограниченным количеством composed controls
- Tier 3: admin-heavy surfaces
  - dense data tables
  - advanced filtering
  - complex CRUD drawers/modals
  - pages с высокой плотностью AntD-specific interactions

## Readiness Gates
Surface считается migration-ready только если подтверждены:
- keyboard navigation и focus management;
- label/aria semantics;
- parity destructive/confirm flows;
- workable automated tests;
- приемлемый bundle impact;
- отсутствие заметной деградации DX для команды.

## Risks
- Команда может недооценить стоимость переписывания сложных `Ant Design` workflows.
- Двухсистемный UI период может привести к визуальной неоднородности без централизованных tokens.
- Ранний перевод сложных CRUD-heavy экранов может замедлить поставку и ухудшить UX.

## Open Questions
- Какой именно pilot screen даст лучший сигнал о DX/UX-cost при минимальном риске для продукта.
- Нужен ли отдельный lint/import rule для ограничения новых direct imports из `antd` и raw `shadcn` primitives.
