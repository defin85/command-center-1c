# TODO: Phase 8 — Миграция/депрекация legacy `ibcmd_*` (переход на schema-driven `ibcmd_cli`)

Связано:
- `docs/roadmaps/ROADMAP_IBCMD_SCHEMA_DRIVEN_COMMANDS.md` (Phase 8)

Цель:
- полностью уйти от operation types вида `ibcmd_*`;
- оставить единый schema-driven путь: `ibcmd_cli` + driver-catalog v2 (`command_id + params`);
- вместо “предустановленных” `ibcmd_*` дать пользователям возможность создавать свои “ссылки/шорткаты” (presets) на команды.

Сроки (предложение, можно скорректировать):
- Deprecation: 2026-01-08 (введено)
- Sunset: 2026-04-01 (после этой даты удаляем legacy endpoint/типы и остатки кода)

Примечание по статусам:
- `[ ]` — не сделано
- `[x]` — сделано

---

## 0) Границы и правила депрекации

- [x] Создан checklist Phase 8
- [x] Зафиксировать окно совместимости и дату `Sunset` для legacy `ibcmd_*` (Sunset: 2026-04-01)
- [ ] Определить “definition of done” для Phase 8 (технические критерии снятия legacy)
- [ ] Согласовать UX правило: legacy `ibcmd_*` полностью скрыты от non-staff, видны только при compat/миграции

---

## 1) Инвентаризация и маппинг legacy → catalog `command_id`

- [x] Составить таблицу соответствий `ibcmd_*` → `ibcmd.<...>` (стабильные `command_id`)
- [x] Зафиксировать правила переноса payload (поля, defaults, masking, artifact://) в коде (`apps/operations/ibcmd_legacy.py`)
- [x] Добавить юнит-тесты на маппинг (legacy endpoint → `ibcmd_cli` operation)
- [x] Добавить метрику/счётчик “legacy usage” по каждому `ibcmd_*`

Touchpoints (as-is):
- `orchestrator/apps/api_v2/views/operations.py` (UI meta, каталог операций)
- `orchestrator/apps/templates/workflow/handlers/backends/ibcmd.py` (legacy backend)
- `go-services/worker/internal/drivers/ibcmdops/driver.go` (legacy driver)
- `frontend/src/pages/Operations/components/NewOperationWizard/types.ts` (enum `OperationType`)
- `contracts/orchestrator/openapi.yaml` (execute-ibcmd / enums `ibcmd_*`)
- `docs/ibcmd.md` (документация legacy)

---

## 2) Orchestrator: compat-слой + явная депрекация

- [x] Добавить нормализацию: любые `ibcmd_*` транслировать в `ibcmd_cli` (один путь исполнения)
- [x] Добавить HTTP-сигналы депрекации (`Deprecation`/`Sunset` headers) для legacy endpoint/типов
- [x] Пометить legacy операции в каталоге как deprecated (и скрывать в UI для non-staff)
- [x] Запретить создание новых legacy `ibcmd_*` (server-side: legacy endpoint/типы создают только `ibcmd_cli`)
- [x] Добавить аудит: фиксировать факт “legacy compat” при запуске операции (Prometheus + metadata)

---

## 3) UI: убрать `ibcmd_*` и добавить user-created links (shortcuts/presets)

### 3.1 Удаление/скрытие legacy

- [ ] Убрать `ibcmd_*` из пользовательских UI путей (Wizard/каталог/поиск)
- [ ] Отобразить предупреждение/баннер при открытии старых операций (если они ещё есть в истории)
- [ ] Обеспечить обратную совместимость отображения истории/логов для уже созданных legacy операций

### 3.2 Links/Presets (пользовательские “ссылки”)

- [x] Определить модель данных “ссылки” (per-user, MVP): `driver`, `command_id`, `title` (без секретов)
- [x] Добавить UI: создание ссылки из формы команды (“Save as shortcut”)
- [x] Добавить UI: список ссылок (MVP), загрузка и удаление
- [x] RBAC: скрывать ссылки, если пользователь больше не имеет доступа к `command_id` или target-объекту

---

## 4) Миграция данных: Templates / Workflows / Artifacts

- [ ] Найти все места, где сериализуются/хранятся `ibcmd_*` в Template/Workflow/Artifact payload
- [ ] Реализовать миграцию: переписать `ibcmd_*` → `ibcmd_cli + command_id + params`
- [ ] Добавить dry-run режим (отчёт: сколько объектов будет изменено, какие типы встречаются)
- [ ] Добавить “idempotent” гарантию (повторный прогон не ломает данные)
- [ ] Добавить тесты на миграцию (минимум: 1–2 fixtures)

---

## 5) Worker: удаление legacy driver и унификация исполнения

- [ ] Убедиться, что `ibcmd_cli` полностью покрывает нужные сценарии legacy (артефакты, masking, прогресс)
- [ ] Удалить/заморозить `ibcmdops` driver после окончания окна совместимости
- [ ] Удалить старые code paths и тесты, завязанные на `ibcmd_*`

---

## 6) OpenAPI + документация + коммуникация

- [x] Пометить legacy в `contracts/orchestrator/openapi.yaml` как deprecated (и указать срок `Sunset`)
- [x] Обновить `docs/ibcmd.md`: новый путь (`ibcmd_cli`), каталоги команд, shortcuts, миграция
- [x] Добавить “migration notes” для пользователей (что меняется, как создать ссылку вместо `ibcmd_*`)

---

## 7) Удаление legacy (финальный чеклист)

- [ ] Метрики показывают 0 (или приемлемый порог) legacy запусков за период
- [ ] Запрещено создание новых legacy, миграция данных завершена
- [ ] Удалены: enums `ibcmd_*` из UI/контрактов, endpoints/ветки кода, документация legacy
- [ ] Добавлен/обновлён smoke-test на выполнение `ibcmd_cli` по каталогу (sanity)
