# Execution Plans

Статус: authoritative agent-facing guidance.

Используй этот template для длинных, неоднозначных или multi-step задач, прежде чем переходить к реализации.

## Когда нужен plan

- change затрагивает несколько подсистем
- есть архитектурная неоднозначность
- есть rollout, migration или compatibility risk
- есть несколько обязательных validation gates

## Canonical Template

```markdown
# Plan: <краткое название>

## Scope
- Что входит в change
- Что не входит в change

## Assumptions
- Явные предположения, без которых нельзя двигаться

## Constraints
- Спецификации, contracts, runtime limits, approval gates

## Ordered Steps
1. <шаг>
2. <шаг>
3. <шаг>

## Verification Checkpoints
- После шага 1: <команда / критерий>
- После шага 2: <команда / критерий>

## Blockers / Open Questions
- Что может остановить работу
- Что требует отдельного решения
```

## Правила

- Держи один plan на одну coherent task.
- Обновляй plan по мере изменений в understanding.
- Не начинай реализацию mandatory behavior без связи `Requirement -> Step -> Verification`.

