## Контекст
- Текущий frontend governance уже умеет ловить generic shell violations для `ModalFormShell` / `DrawerFormShell`.
- Route-level governance остаётся в основном path-based: правила перечисляют конкретные page files и migration zones.
- Из-за этого активные migration wave вынуждены каждый раз вручную расширять `eslint.config.js`, а новый route может временно оказаться вне monitoring perimeter.

## Goals / Non-Goals

### Goals
- Сделать repo-wide monitoring perimeter явным для всего operator-facing frontend.
- Обеспечить, что ни один route-entry module и ни одна shell-backed authoring surface не остаются без governance classification.
- Развести общий safety monitoring и более строгий platform-governed tier, чтобы не смешивать "мониторить" и "полностью мигрировать".

### Non-Goals
- Не переводить весь frontend на `WorkspacePage` / `DashboardPage` в рамках одного change.
- Не объявлять все legacy routes сразу `platform-governed`.
- Не заменять browser-level runtime checks линтером для state restore, responsive fallback и shell-safe handoff.

## Decisions

### 1. Единый governance inventory
Repo-wide monitoring должен опираться на checked-in inventory, который перечисляет:
- operator-facing route-entry modules;
- shell-backed authoring surfaces;
- governance tier для каждого surface.

Inventory должен проверяться автоматически против route map и исходников, чтобы новый route нельзя было добавить "мимо" governance.

### 2. Tiered governance вместо одномоментного ужесточения всего UI
Используются три класса:
- `platform-governed` — строгий route-level contract для уже migrated surfaces;
- `legacy-monitored` — общий safety monitoring для legacy pages, которые ещё не переведены на platform shell;
- `excluded` — только public/helper path, generated code или другие явно разрешённые исключения.

Такой подход позволяет мониторить весь frontend сейчас, не обещая миграцию всего frontend за один change.

### 3. Generic rules против file-specific hardcode там, где это возможно
Для shell-backed authoring surfaces repo-wide generic rule уже оправдан и должен стать базовым contract для всех page family.

Для route-page нужен гибрид:
- общие repo-wide safety checks;
- tier-specific restrictions для `platform-governed` routes;
- automated inventory drift checks вместо молчаливых ad-hoc gaps.

### 4. Validation должна ловить coverage drift, а не только raw violations
Недостаточно проверять только forbidden imports. Validation должна также падать, если:
- route map и governance inventory расходятся;
- новый route не получил governance tier;
- `excluded` используется для operator-facing path без допустимого основания.

## Alternatives Considered

### Продолжать расширять `eslint.config.js` вручную по migration wave
Отклонено. Это оставляет окна между wave и не даёт честного ответа на вопрос, мониторит ли линтер весь frontend.

### Сразу объявить весь frontend `platform-governed`
Отклонено. Это смешивает governance coverage с полной migration и делает change чрезмерно широким.

## Risks / Trade-offs
- Inventory добавляет служебный слой, который нужно поддерживать в актуальном состоянии.
- Tier system может превратиться в скрытую allowlist, если `excluded` будет использоваться слишком свободно.
- Repo-wide enforcement затронет активные migration change, поэтому нужно явно описать, что этот change даёт общую инфраструктуру, а не отменяет route-specific migration work.

## Migration Plan
1. Ввести inventory и tier classification.
2. Доработать lint/plugin/tests так, чтобы missing classification и drift стали blocking failures.
3. Классифицировать текущие route-entry и shell-backed surfaces.
4. Использовать этот inventory как shared basis для следующих migration wave.

## Open Questions
- Нет.
