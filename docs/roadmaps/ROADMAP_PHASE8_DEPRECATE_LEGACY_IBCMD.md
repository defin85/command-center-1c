# TODO: Phase 8 — Удаление legacy `ibcmd_*` (переход на schema-driven `ibcmd_cli`)

Связано:
- `docs/roadmaps/ROADMAP_IBCMD_SCHEMA_DRIVEN_COMMANDS.md` (Phase 8)

Цель:
- полностью уйти от operation types вида `ibcmd_*`;
- оставить единый schema-driven путь: `ibcmd_cli` + driver-catalog v2 (`command_id + params`);
- вместо “предустановленных” `ibcmd_*` дать пользователям возможность создавать свои “ссылки/шорткаты” (presets) на команды.

Сроки (предложение, можно скорректировать):
- Start (stop-new + cleanup): 2026-01-08
- Target finish (cleanup): 2026-01-15

Примечание по статусам:
- `[ ]` — не сделано
- `[x]` — сделано

---

## 0) Границы и правила депрекации

- [x] Создан checklist Phase 8
- [x] Определить “definition of done” для Phase 8 (технические критерии снятия legacy)
  - [x] Удалены legacy endpoints/enum’ы/ветки кода и документация legacy
  - [x] Данные мигрированы (Templates → `ibcmd_cli`), legacy BatchOperation удалены из БД
  - [x] Перегенерены клиенты (routes/TS), пройдены проверки
- [x] Согласовать UX правило: legacy `ibcmd_*` полностью скрыты от non-staff (теперь их нет в каталоге/типах)

---

## 1) Инвентаризация и маппинг legacy → catalog `command_id`

- [x] Составить таблицу соответствий `ibcmd_*` → `command_id` (стабильные `command_id`)
- [x] Зафиксировать правила переноса payload (поля, defaults, masking, artifact://) в миграции Templates и builder’е `ibcmd_cli`
- [x] Добавить тесты: legacy endpoint отсутствует; `operation_type=ibcmd_*` отклоняется

Touchpoints (as-is):
- `orchestrator/apps/api_v2/views/operations.py` (UI meta, каталог операций)
- `orchestrator/apps/templates/workflow/handlers/backends/ibcmd.py` (legacy backend)
- `go-services/worker/internal/drivers/ibcmdops/driver.go` (legacy driver)
- `frontend/src/pages/Operations/components/NewOperationWizard/types.ts` (enum `OperationType`)
- `contracts/orchestrator/openapi.yaml` (execute-ibcmd / enums `ibcmd_*`)
- `docs/ibcmd.md` (документация legacy)

---

## 2) Orchestrator: stop-new + cleanup

- [x] Удалить endpoint `POST /api/v2/operations/execute-ibcmd/`
- [x] Убрать `ibcmd_*` из `ExecuteOperationRequest.operation_type` (и отказ от legacy в серверной логике)
- [x] Удалить legacy код/registry entries: оставлен только `ibcmd_cli`
- [x] Удалить legacy `ibcmd_*` из `BatchOperation.operation_type` (на уровне доменной модели)

---

## 3) UI: убрать `ibcmd_*` и добавить user-created links (shortcuts/presets)

### 3.1 Удаление/скрытие legacy

- [x] Убрать `ibcmd_*` из пользовательских UI путей (Wizard/каталог/поиск)
- [x] Обеспечить обратную совместимость отображения истории (если в БД были legacy операции — они удалены миграцией)

### 3.2 Links/Presets (пользовательские “ссылки”)

- [x] Определить модель данных “ссылки” (per-user, MVP): `driver`, `command_id`, `title` (без секретов)
- [x] Добавить UI: создание ссылки из формы команды (“Save as shortcut”)
- [x] Добавить UI: список ссылок (MVP), загрузка и удаление
- [x] RBAC: скрывать ссылки, если пользователь больше не имеет доступа к `command_id` или target-объекту

---

## 4) Миграция данных: Templates / Workflows / Artifacts

- [x] Реализовать миграцию Templates: переписать `ibcmd_*` → `ibcmd_cli + command_id + params`
- [x] Удалить legacy `BatchOperation` из БД (data migration)

---

## 5) Worker: удаление legacy driver и унификация исполнения

- [x] Убедиться, что `ibcmd_cli` покрывает нужные сценарии legacy (artifact://, masking, прогресс)
- [x] Удалить старые code paths, завязанные на `ibcmd_*` (оставлен только `ibcmd_cli`)

---

## 6) OpenAPI + документация + коммуникация

- [x] Удалить legacy из `contracts/orchestrator/openapi.yaml` (paths + enums)
- [x] Перегенерить клиентов (routes/TS)
- [x] Обновить `docs/ibcmd.md` под `ibcmd_cli`

---

## 7) Удаление legacy (финальный чеклист)

- [x] Запрещено создание новых legacy (endpoint/enum’ы удалены)
- [x] Миграция данных завершена (Templates) + legacy BatchOperation удалены из БД
- [x] Удалены: enums `ibcmd_*` из UI/контрактов, endpoints/ветки кода, документация legacy
- [ ] Добавлен/обновлён smoke-test на выполнение `ibcmd_cli` по каталогу (sanity)
