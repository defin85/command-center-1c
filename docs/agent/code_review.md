# Code Review Checklist

Статус: authoritative agent-facing guidance.

## Profile-Aware Expectations

- `analysis/review`: findings-first ответ, file references, assumptions и residual uncertainty без искусственного delivery overhead.
- `local change`: focus на bugs/regressions, coverage gaps, doc drift и достаточность минимального check set.
- `delivery`: полный acceptance mindset с `Requirement -> Code -> Test`, Beads/OpenSpec alignment и проверкой delivery actions.

## Bugs And Regressions

- Изменение не ломает существующие entry points, contracts и runtime flows.
- Нет ошибок в новых путях выполнения, edge cases и отрицательных сценариях.
- Нет рассинхрона между intended behavior и фактической реализацией.

## Requirement Traceability

- Каждый обязательный Requirement/Scenario покрыт кодом или явным approved exception.
- Есть явная связь `Requirement -> Code -> Test`.

## Validation

- Запущен минимально достаточный набор проверок для выбранного completion profile.
- Не пропущены lint, tests, browser checks или runtime probes, если они релевантны.
- Дифф не принят без проверки итогового behavior.

## Contracts And Data

- Не сломаны API contracts, schema assumptions, generated clients и machine-readable inventories.
- Нет скрытых changes в портах, entry points, verification commands и runtime mapping.

## Maintainability

- Нет лишнего broad refactor вне задачи.
- Локальные инструкции и docs обновлены, если change меняет workflow, verification path или source-of-truth references.
- Новые skills или docs остаются bounded и одноцелевыми.

## Delivery Readiness

- Для `local change` и `delivery` понятно, какие файлы были изменены и почему выбран именно этот validation scope.
- Для `delivery` Beads/OpenSpec status отражают реальное состояние change.
- Для `delivery` final handoff не скрывает blockers и не подменяет evidence общим summary.
