---
name: openspec-change-delivery
description: Use when implementing an approved OpenSpec change end-to-end through execution matrix, Beads tracking, targeted verification, and final Requirement -> Code -> Test handoff.
---

# OpenSpec Change Delivery

## What This Skill Does

Пакует repeatable workflow для approved OpenSpec change: execution matrix, Beads-driven delivery, targeted verification и финальный `Requirement -> Code -> Test` handoff.

## When To Use

Используй, когда пользователь просит:

- "реализуй approved change"
- "делай всё по change-id"
- "применяй OpenSpec change"
- "веди задачу через OpenSpec и Beads"

## Inputs

- `change-id`
- approved `proposal.md`, `tasks.md`, `specs/**/spec.md`
- текущий Beads graph или команда на его создание

## Outputs

- execution matrix `Requirement -> files -> checks`
- обновлённый статус задач в `bd`
- список прогнанных validation commands
- финальный traceability report

## Workflow

1. Прочитай `proposal.md`, `tasks.md`, `design.md` и delta specs.
2. Построй execution matrix до начала правок.
3. Работай от `bd ready`; newly discovered work оформляй отдельным issue.
4. После каждого логического шага обновляй docs и validation path, если change меняет workflow или contracts.
5. Прогони минимальный релевантный набор проверок, затем более широкий gate.
6. Перед handoff подготовь `Requirement -> Code -> Test`.

## Success Criteria

- все mandatory requirements покрыты кодом и проверками
- `bd` отражает реальный статус задач
- финальный отчёт содержит traceability и validation results

## Practical Job

Пример: "Реализуй approved OpenSpec change end-to-end, веди работу через Beads и отдай финальный `Requirement -> Code -> Test` отчёт."
