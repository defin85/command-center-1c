## Context
Текущий frontend уже построен на `React 18 + TypeScript + Vite + Ant Design`. В `frontend/package.json` уже присутствуют `antd` и `@ant-design/pro-components`, однако `pro-components` фактически не используются как системный слой композиции.

По наблюдаемому состоянию UI проблема не в нехватке отдельных компонентов, а в отсутствии platform boundary:
- страницы собираются напрямую из raw `antd` primitives;
- page patterns (`list/detail/master-detail/edit`) не стандартизованы;
- responsive fallback определяется ad-hoc;
- проверяемые правила почти не формализованы;
- отсутствие guardrails позволяет фронту и дальше накапливать несовместимые решения.

Внешние ориентиры подтверждают выбор Ant-based направления:
- Ant Design `Data List` рекомендует выбирать между split/detail, drawer и отдельной страницей по плотности контента и длине detail surface, а не смешивать все режимы в одном потоке.
- Ant Design имеет `Splitter`, но он доступен только в более новых версиях Ant 5; текущая версия `antd` в репозитории (`^5.12.0`) не позволяет опираться на него без осознанного upgrade.
- Актуальная линия `@ant-design/pro-components` поддерживает `antd` в диапазоне Ant 5 и не даёт подтверждённого peer-окна для неподтверждённого major jump, поэтому platform baseline должен обновлять Ant внутри поддерживаемой современной `5.x` линии.
- `@ant-design/pro-components` покрывает типовые enterprise/admin patterns (`ProTable`, `ProDescriptions`, `ProCard`, `ProForm`) и лучше согласуется с текущим стеком, чем ввод второй design system.
- `shadcn/ui` требует отдельного foundation на базе `Tailwind CSS` и open-code primitives; это полезно для собственного design system, но в текущем репозитории означало бы конкурирующую платформу, а не thin layer над уже принятой.
- `Refine` полезен как CRUD framework, но не решает сам по себе задачу единого UI platform layer для mixed product surfaces и не должен становиться обязательным основанием для всех нестандартных экранов.

## Goals / Non-Goals
- Goals:
  - Зафиксировать canonical UI platform: `antd` + `@ant-design/pro-components` + thin design layer.
  - Зафиксировать ограниченный набор canonical page patterns и responsive contract.
  - Ввести blocking lint/CI validation для архитектурных UI-границ.
  - Ввести явные UI instructions в `AGENTS.md`.
  - Подготовить управляемую миграцию пилотных surfaces (`/decisions`, `/pools/binding-profiles`) без big-bang rewrite.
- Non-Goals:
  - Полный rewrite всех страниц.
  - Введение `shadcn/ui`/`Tailwind CSS` как параллельной foundation.
  - Навязывание `Refine` как обязательного framework-wide abstraction.
  - Решение всех визуальных дефектов только линтером.

## Decisions

### 1. Canonical UI platform = Ant-based stack
Новые и существенно переписываемые backoffice surfaces должны строиться на `antd` + `@ant-design/pro-components` через project-owned thin design layer.

Это даёт:
- минимальную цену внедрения относительно текущего кода;
- reuse уже существующего vendor stack;
- единый набор form/table/detail patterns;
- отсутствие второй параллельной design system.

Dependency baseline этого стека ДОЛЖЕН (SHALL) обновить `antd` до поддерживаемой современной `5.x` линии, совместимой с актуальной линией `@ant-design/pro-components`. Переход на неподтверждённую major-версию `antd` не входит в этот change.

### 2. Thin design layer становится обязательной точкой композиции
Thin layer должен инкапсулировать:
- page shells (`PageHeader`, `PageSection`, `WorkspacePage`);
- entity patterns (`EntityTable`, `EntityDetails`, `MasterDetailShell`);
- editing patterns (`DrawerFormShell`, `ModalFormShell`);
- shared semantics (`StatusBadge`, `ErrorState`, `EmptyState`, `JsonBlock`).

Raw vendor imports не запрещаются глобально для всего legacy-кода, но new/rewritten surfaces должны идти через thin layer как primary path.

### 3. `MasterDetail` получает обязательный responsive fallback
Для data-heavy surfaces `MasterDetail` допускается как canonical pattern, но:
- detail/edit не должен появляться как inline-блок ниже всей страницы;
- narrow viewport обязан переключать detail/edit в `Drawer`, off-canvas panel или отдельный route/state;
- горизонтальный overflow не считается допустимым mobile behaviour.

### 4. Governance строится на сочетании lint + browser tests + AGENTS guidance
Не все UI-инварианты проверяются линтером. Поэтому слой governance делится на три части:
- `eslint` для архитектурных границ (`no-restricted-imports`, `no-restricted-syntax`, запреты на raw composition patterns);
- browser tests для responsive/overflow и interaction invariants;
- `AGENTS.md` как человеческий и агентный контракт по canonical patterns.

### 5. Competing primary UI foundation не допускается без отдельного approved architectural change
Параллельное внедрение второй primary UI foundation создаст две primary design systems и усугубит drift.

Ant-based platform в рамках этого change считается единственным approved direction для новых platform migrations, пока отдельный approved architectural change не зафиксирует другое решение.

## Alternatives Considered

### Вариант A: Оставить чистый `antd` без thin layer
Плюсы:
- минимальные стартовые изменения.

Минусы:
- не устраняет platform drift;
- сохраняет прямую page-level композицию из vendor components;
- плохо поддаётся lint enforcement на уровне “какие страницы как строятся”.

Итог: недостаточно.

### Вариант B: Перейти на `shadcn/ui`
Плюсы:
- project-owned primitives;
- высокая визуальная свобода.

Минусы:
- в текущем проекте это вторая competing design system;
- требует `Tailwind CSS` и нового foundation/tooling;
- дороже по migration, тестам и visual parity.

Итог: отклонён для этого change.

### Вариант C: Взять `Refine` как главный путь
Плюсы:
- сильные CRUD abstractions;
- полезные готовые hooks/forms/tables.

Минусы:
- framework-level conventions поверх существующего приложения;
- не покрывает хорошо нестандартные surfaces сам по себе;
- избыточен как обязательный foundation для всей UI platform.

Итог: допустим только как отдельный точечный выбор в будущем, но не как базовое решение этого change.

## Risks / Trade-offs
- Thin design layer добавляет ещё один слой абстракции; если сделать его слишком толстым, он превратится в “внутренний framework”.
  - Mitigation: слой должен быть тонким и pattern-oriented, а не заменять весь `antd`.
- Не все правила проверяются линтером.
  - Mitigation: фиксировать, какие инварианты lintable, а какие обязаны жить в Playwright/a11y tests.
- Текущая версия `antd` ограничивает использование официального `Splitter`, а неправильный major upgrade может нарушить совместимость с `pro-components`.
  - Mitigation: зафиксировать обязательный upgrade `antd` внутри поддерживаемой современной `5.x` линии и не делать `Ant 6` частью этого change.
- Риск появления второй competing primary UI foundation параллельно с Ant-based platform.
  - Mitigation: явно зафиксировать single-primary-direction policy в spec, lint/governance и `AGENTS.md`.

## Migration Plan
1. Зафиксировать capability/spec contract для Ant-based platform и governance.
2. Добавить thin design layer и lint rules.
3. Добавить `AGENTS.md` UI block и blocking validation path.
4. Провести pilot migration на `/decisions`.
5. Провести pilot migration на `/pools/binding-profiles`.
6. После успешных pilot surfaces масштабировать подход на остальные CRUD/admin surfaces.

## Open Questions
- Какой именно target baseline внутри современной `antd 5.x` линии проект принимает как минимально обязательный для implementation этого change?
