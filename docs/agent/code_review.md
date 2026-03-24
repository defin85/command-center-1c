# Code Review Checklist

Статус: authoritative agent-facing guidance.

Используй этот checklist для `/review`, acceptance review и self-review перед handoff.

## Bugs And Regressions

- Изменение не ломает существующие entry points, contracts и runtime flows.
- Нет ошибок в новых путях выполнения, edge cases и отрицательных сценариях.
- Нет рассинхрона между intended behavior и фактической реализацией.

## Requirement Traceability

- Каждый обязательный Requirement/Scenario покрыт кодом или явным approved exception.
- Есть явная связь `Requirement -> Code -> Test`.

## Validation

- Запущен минимально достаточный набор проверок.
- Не пропущены lint, tests, browser checks или runtime probes, если они релевантны.
- Дифф не принят без проверки итогового behavior.

## Contracts And Data

- Не сломаны API contracts, schema assumptions, generated clients и machine-readable inventories.
- Нет скрытых changes в портах, entry points, verification commands и runtime mapping.

## Maintainability

- Нет лишнего broad refactor вне задачи.
- Локальные инструкции и docs обновлены, если change меняет workflow или verification path.
- Новые skills или docs остаются bounded и одноцелевыми.

