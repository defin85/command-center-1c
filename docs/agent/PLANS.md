# Execution Plans

Статус: authoritative agent-facing guidance.

## Choose Completion Profile First

- `analysis/review`: план может быть лёгким, но должен фиксировать evidence path и open questions.
- `local change`: план должен показать scope правок, validation path и docs/contracts sync points.
- `delivery`: план обязан держать связь `Requirement -> Step -> Verification`, Beads/OpenSpec alignment и final handoff expectations.
- Approved OpenSpec change implementation по умолчанию идёт как `delivery`.

## Когда нужен plan

- change затрагивает несколько подсистем
- есть архитектурная неоднозначность
- есть rollout, migration или compatibility risk
- есть несколько обязательных validation gates
- есть delivery work через OpenSpec/Beads

## Canonical Template

```markdown
# Plan: <краткое название>

## Completion Profile
- `analysis/review` | `local change` | `delivery`

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
- Обновляй plan по мере изменения understanding.
- Не начинай mandatory behavior без связи `Requirement -> Step -> Verification`.
- Если task-class меняется по ходу работы, обнови completion profile, а не только ordered steps.
