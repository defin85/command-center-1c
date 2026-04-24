---
name: runtime-debug
description: "Use to inspect, restart, and verify local frontend/backend runtimes with targeted probes."
---

# Runtime Debug

## What This Skill Does

Пакует стандартный локальный runtime-debug workflow для CommandCenter1C: inventory, probe, restart, targeted eval и итоговую проверку.

## When To Use

Используй, когда пользователь просит:

- "проверь рантаймы"
- "посмотри, почему сервис не отвечает"
- "перезапусти orchestrator/api-gateway/worker/frontend"
- "сделай runtime debug"

## Inputs

- имя рантайма или симптом
- при необходимости точечная команда проверки

## Outputs

- summary по состоянию рантайма
- список использованных команд
- следующий verification step или найденный blocker

## Workflow

1. Сверься с `docs/agent/RUNBOOK.md` и `DEBUG.md`.
2. Получи текущую карту рантаймов через `./debug/runtime-inventory.sh --json`.
3. Выполни `./debug/probe.sh all` или точечный `./debug/probe.sh <runtime>`.
4. Если нужен restart, используй `./debug/restart-runtime.sh <runtime>` или `./scripts/dev/restart.sh <runtime>`.
5. Для короткой runtime-проверки используй:
   - `./debug/eval-django.sh "<python code>"`
   - `./debug/eval-frontend.sh "<js expression>"`
6. Подтверди итог probe/eval после изменений.

## Success Criteria

- состояние рантайма подтверждено probe или eval
- если был restart, после него выполнена повторная проверка
- в отчёте указано, healthy ли рантайм и что делать дальше

## Practical Job

Пример: "Проверь, почему frontend не отвечает на `http://localhost:15173`, и если нужно, перезапусти его и подтверди health."
