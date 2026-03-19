## Context
`/pools/binding-profiles` уже был частью предыдущей usability migration, но после реального UI audit осталось несколько дефектов, которые не закрываются текущими specs:
- default revision history всё ещё выводит opaque immutable pin на основном detail path;
- narrow-viewport detail drawer допускает clipping primary action row и опирается на внутренний overflow secondary blocks;
- page и shared shell имеют воспроизводимые accessibility violations по contrast, heading order и visible-label/accessibility-name parity.

Эти дефекты не требуют новой архитектуры backend или broad UI redesign, но они уже влияют на operator-facing quality и не должны оставаться “просто implementation detail”.

Одновременно в репозитории уже есть более широкий pending change `refactor-ui-platform-operational-workspaces`. Новый change не должен дублировать его scope. Поэтому этот proposal intentionally остаётся узким: remediation только для `/pools/binding-profiles` и только для тех shared shell/platform pieces, без которых страница не проходит audit.

## Goals / Non-Goals
- Goals:
  - Зафиксировать summary-first default detail contract для `/pools/binding-profiles`.
  - Убрать immutable opaque ids из primary operator path, не ломая runtime lineage.
  - Сделать inspect/revise/deactivate flow на narrow viewport реально usable.
  - Закрыть audit-detected a11y defects страницы и shared shell, которые прямо на ней воспроизводятся.
- Non-Goals:
  - Переделывать всю навигационную оболочку приложения.
  - Широко пересматривать все typography/color tokens проекта.
  - Расширять change на соседние routes.
  - Менять доменный backend contract binding profiles.

## Decisions

### 1. Summary-first detail остаётся default, technical lineage уходит в advanced disclosure
Immutable ids и raw payload нужны для runtime/support/debugging, но не для primary operator inspection.

Поэтому default detail path должен:
- показывать human-readable revision number, workflow summary, usage summary и next actions;
- не использовать opaque pin как primary column на default revision-history view;
- оставлять immutable ids доступными в explicit advanced disclosure.

Это решение не противоречит существующему spec: opaque id остаётся authoritative runtime identity, но перестаёт быть ранним operator-facing content.

### 2. Mobile-safe detail path важнее, чем полное устранение любого secondary internal scroll
Для data-heavy surfaces secondary tabular content иногда неизбежно требует controlled internal overflow. Но primary operator path не должен зависеть от него.

Для `/pools/binding-profiles` это означает:
- primary action row в drawer обязана wrap/stack without clipping;
- summary fields и next-step controls должны быть полностью доступны без горизонтального скролла;
- если secondary tables всё ещё скроллятся внутренне, это допустимо только как secondary diagnostics/read-model, а не как блокер для inspect/revise/deactivate flow.

### 3. Shared-shell accessibility defects исправляются в общих примитивах, а не page-local workaround’ами
Часть audit findings живёт не в самой странице, а в shared shell/theme:
- stream status control имеет visible-label/accessibility-name mismatch;
- contrast defects затрагивают shared states (`StatusBadge`, selected nav, primary CTA, subtitle tone).

Исправлять это one-off override’ами в `/pools/binding-profiles` было бы неверно. Если проблема приходит из shared shell или shared primitive, remediation должен идти там же, но без расширения scope на unrelated redesign.

### 4. Change вводит только минимальные новые UI guidelines
Новый change не должен превращаться в universal accessibility rewrite. Поэтому в `ui-web-interface-guidelines` добавляются только те contracts, которые прямо нужны для этих findings:
- visible text label и accessible name не расходятся;
- heading hierarchy идёт последовательно;
- operator-facing text/state/action labels на platform-governed surfaces и shared shell проходят WCAG AA contrast.

Это минимальный набор правил, который делает findings enforceable и проверяемыми.

## Alternatives Considered

### Вариант A: Чинить страницу без нового spec change
Плюсы:
- быстрее начать код.

Минусы:
- defects снова останутся implementation-local;
- hardening не будет закреплён как source-of-truth;
- сложно проверять, что следующий refactor не вернёт те же проблемы.

Итог: отклонён.

### Вариант B: Включить все audit findings в `refactor-ui-platform-operational-workspaces`
Плюсы:
- меньше changes в OpenSpec.

Минусы:
- смешивает узкий remediation с broad migration wave;
- увеличивает размер и задержку already pending change;
- page-specific issues рискуют потеряться среди более крупных workstreams.

Итог: отклонён.

### Вариант C: Широко переписать theme/token system ради contrast
Плюсы:
- можно закрыть contrast системно.

Минусы:
- несоразмерно текущему аудиту;
- легко расширяет scope на весь shell и все routes.

Итог: отклонён. Предпочтителен минимальный shared remediation, достаточный для affected page.

## Risks / Trade-offs
- Contrast fixes через shared theme/tokens могут затронуть визуальное поведение других страниц.
  - Mitigation: менять только явно проблемные shared states и проверять affected routes минимальным regression set.
- Удаление opaque pin из default revision table может вызвать опасение потери support visibility.
  - Mitigation: pin остаётся доступным в advanced disclosure и не исчезает из продукта.
- Mobile drawer remediation может потребовать менять shared primitive behaviour.
  - Mitigation: ограничить изменение `MasterDetailShell` / related primitives только тем, что нужно для primary usability, без broad layout rewrite.

## Migration Plan
1. Обновить spec contracts для page-local и shared accessibility expectations.
2. Исправить shared shell/theme/primitives, которые формируют findings на странице.
3. Переделать default detail path `/pools/binding-profiles`.
4. Добавить browser/unit coverage на mobile drawer, technical disclosure и a11y contracts.
5. Прогнать blocking frontend validation gate.
