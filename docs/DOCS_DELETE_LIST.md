# 🗑️ Список файлов на ПОЛНОЕ УДАЛЕНИЕ

**Дата:** 2025-10-31
**Причина:** Очистка от неактуальной/незавершённой документации

---

## ❌ УДАЛИТЬ ПОЛНОСТЬЮ (не архивировать)

### 1. Installation Service (183KB, 7 файлов)

**Причина:** Сервис не завершён, не используется, будет переделан в Phase 4

**Документация на удаление:**
- `docs/INSTALLATION_SERVICE_DESIGN.md` (48KB) ❌
- `docs/INSTALLATION_SERVICE_SUMMARY.md` (27KB) ❌
- `docs/INSTALLATION_SERVICE_TESTING.md` (26KB) ❌
- `docs/INSTALLATION_SERVICE_CODE_REVIEW.md` (52KB) ❌
- `docs/INSTALLATION_SERVICE_DEPLOYMENT.md` (30KB) ❌
- `go-services/installation-service/README.md` (8KB) ❌
- `go-services/installation-service/QUICKSTART.md` (8KB) ❌

**Код на удаление:**
```bash
rm -rf go-services/installation-service/
```

**Итого:** 183KB документации + весь код сервиса

---

### 2. IBIS Service (111KB, 2 файла)

**Причина:** Сервис не начат, Phase 2-3 feature, концепция устарела

**Документация на удаление:**
- `docs/IBIS_SERVICE_ARCHITECTURE.md` (72KB) ❌ ← САМЫЙ БОЛЬШОЙ ФАЙЛ
- `docs/IBIS_SERVICE_GO_ARCHITECTURE.md` (39KB) ❌

**Код:** Нет (сервис не создавался)

**Итого:** 111KB документации

---

### 3. Устаревшие Sprint документы (33KB, 4 файла)

**Причина:** Информация полностью дублируется в SPRINT_1_PROGRESS.md

**Файлы:**
- `SPRINT_1.2_DOCKER_INTEGRATION.md` (8KB) ❌
  - Дублирует Sprint 1.2 секцию в SPRINT_1_PROGRESS.md

- `docs/sprint_1_2_day_1_COMPLETED.md` (7KB) ❌
  - Устарел, есть в SPRINT_1_PROGRESS.md

- `docs/ROADMAP_DIAGRAMS.md` (26KB) ❌
  - Диаграммы устарели, не обновлялись после Sprint 1.4
  - Можно воссоздать при необходимости

- `docs/CURRENT_STATE_DIAGRAM.md` (13KB) ❌
  - Устарел (2025-10-28), не отражает Sprint 1.4 changes
  - Endpoint management не отражён

**Итого:** 54KB

---

### 4. Endpoint Management детали (73KB, 5 файлов)

**Причина:** Детальная документация процесса решения. Финальное решение уже в SPRINT_1_PROGRESS.md

**Файлы:**
- `docs/ENDPOINT_ID_SOLUTION.md` (7KB) ❌
  - Промежуточное решение

- `docs/ENDPOINT_MANAGEMENT_FLOW.md` (35KB) ❌
  - Детальные диаграммы flow, избыточно

- `docs/RAS_GRPC_GW_FIX.md` (8KB) ❌
  - Техническая деталь исправления

- `docs/APPLY_RAS_GRPC_GW_FIX.md` (11KB) ❌
  - Инструкция по применению fix (устарела после интеграции)

- `docs/ENDPOINT_MANAGEMENT_SOLUTION_SUMMARY.md` (12KB) ❌
  - Дублирует SPRINT_1_PROGRESS.md Sprint 1.4

**Оставить ТОЛЬКО:**
- `docs/ENDPOINT_MANAGEMENT_ARCHITECTURE.md` (19KB) ✅
  - Обновить с финальным решением
  - Сделать reference документом

**Итого:** 73KB удаляем, 19KB обновляем

---

### 5. Demo и Test Reports (45KB, 3 файла)

**Причина:** Demo environment устарел, тесты не актуальны

**Файлы:**
- `demo/README.md` (11KB) ❌
  - Mock OData server больше не используется

- `demo/TEST_REPORT.md` (16KB) ❌
  - Тестирование mock server (2025-10-17)

- `orchestrator/TEST_REPORT.md` (18KB) ❌
  - Django REST API tests (2025-10-20)
  - Устарели после cluster-service integration

**Итого:** 45KB

---

### 6. Дубликаты / избыточные (4KB, 1 файл)

**Файлы:**
- `QUICKSTART.md` (4KB) ❌
  - Полностью дублирует `START_HERE.md`
  - Можно объединить в один файл

**Итого:** 4KB

---

## 📊 Итого на УДАЛЕНИЕ

| Категория | Файлов | Размер | Причина |
|-----------|--------|--------|---------|
| Installation Service | 7 + код | 183KB | Не завершён, будет переделан |
| IBIS Service | 2 | 111KB | Не начат, концепция устарела |
| Sprint docs | 4 | 54KB | Дублируют SPRINT_1_PROGRESS |
| Endpoint details | 5 | 73KB | Промежуточные документы |
| Demo/Tests | 3 | 45KB | Устарели |
| Дубликаты | 1 | 4KB | Избыточность |
| **ВСЕГО** | **22** | **470KB** | **66% от неактуальных** |

---

## ✅ Что АРХИВИРОВАТЬ (не удалять)

### 1. RAS/RAC Research (86KB, 6 файлов)

**Причина:** Ценная исследовательская работа, может пригодиться

**Файлы:**
- `docs/1C_RAS_vs_RAC.md` (12KB)
- `docs/1C_RAC_COMMANDS.md` (17KB)
- `docs/1C_RAC_SECURITY.md` (6KB)
- `docs/1C_RAS_API_OPTIONS.md` (14KB)
- `docs/1C_RAS_ALL_API_OPTIONS.md` (19KB)
- `docs/1C_RAS_GRPC_SOLUTION.md` (18KB)

**Действие:** АРХИВИРОВАТЬ в `docs/archive/research/ras_rac/`

**После консолидации:** Создать `docs/1C_ADMINISTRATION_GUIDE.md` (краткая версия)

---

### 2. Django Cluster Sync (45KB, 4 файла)

**Причина:** Актуальная функциональность, требует консолидации

**Файлы:**
- `docs/DJANGO_CLUSTER_SYNC.md` (14KB)
- `orchestrator/apps/databases/CLUSTER_SERVICE_IMPLEMENTATION.md` (12KB)
- `orchestrator/apps/databases/CLUSTER_SYNC_IMPLEMENTATION.md` (11KB)
- `orchestrator/apps/databases/CLUSTER_SYNC_SUMMARY.md` (8KB)

**Действие:** ОБЪЕДИНИТЬ → `docs/DJANGO_CLUSTER_INTEGRATION.md`

Оригиналы → АРХИВИРОВАТЬ в `docs/archive/django_cluster_sync/`

---

### 3. OData документация (53KB, 3 файла)

**Причина:** Актуальная функциональность

**Файлы:**
- `orchestrator/apps/databases/odata/README.md` (11KB)
- `orchestrator/apps/databases/odata/IMPLEMENTATION.md` (16KB)
- `docs/TZ_ODATA_AUTOMATION.md` (26KB)

**Действие:** ОБЪЕДИНИТЬ → `docs/ODATA_INTEGRATION.md`

Оригиналы → АРХИВИРОВАТЬ в `docs/archive/odata/`

---

## 🚀 План действий

### Шаг 1: Удаление (приоритет)

```bash
# 1. Installation Service
rm -rf go-services/installation-service/
rm docs/INSTALLATION_SERVICE_*.md
rm go-services/installation-service/*.md

# 2. IBIS Service
rm docs/IBIS_SERVICE_*.md

# 3. Устаревшие Sprint docs
rm SPRINT_1.2_DOCKER_INTEGRATION.md
rm docs/sprint_1_2_day_1_COMPLETED.md
rm docs/ROADMAP_DIAGRAMS.md
rm docs/CURRENT_STATE_DIAGRAM.md

# 4. Endpoint management детали
rm docs/ENDPOINT_ID_SOLUTION.md
rm docs/ENDPOINT_MANAGEMENT_FLOW.md
rm docs/RAS_GRPC_GW_FIX.md
rm docs/APPLY_RAS_GRPC_GW_FIX.md
rm docs/ENDPOINT_MANAGEMENT_SOLUTION_SUMMARY.md

# 5. Demo/Tests
rm -rf demo/
rm orchestrator/TEST_REPORT.md

# 6. Дубликаты
rm QUICKSTART.md
```

**Результат:** -22 файла, -470KB

### Шаг 2: Архивирование

Создать структуру:
```
docs/archive/
├── research/ras_rac/         (6 файлов, 86KB)
├── django_cluster_sync/      (4 файла, 45KB)
└── odata/                    (3 файла, 53KB)
```

### Шаг 3: Консолидация

Создать:
- `docs/1C_ADMINISTRATION_GUIDE.md` (из 6 RAS/RAC файлов)
- `docs/DJANGO_CLUSTER_INTEGRATION.md` (из 4 Django файлов)
- `docs/ODATA_INTEGRATION.md` (из 3 OData файлов)
- `docs/ENDPOINT_MANAGEMENT.md` (обновить ARCHITECTURE.md)

---

## ⚠️ Важные замечания

### НЕ ТРОГАТЬ (критичные файлы):

1. **SPRINT_1_PROGRESS.md** ✅ - полная история Sprint 1.1-1.4
2. **ROADMAP.md** ✅ - главный план
3. **CLAUDE.md** ✅ - инструкции для AI
4. **README.md** ✅ - точка входа
5. **START_HERE.md** ✅ - getting started
6. **EXECUTIVE_SUMMARY.md** ✅ - краткое резюме
7. **INDEX.md** ✅ - навигация
8. **go-services/cluster-service/*** ✅ - актуальный рабочий сервис
9. **go-services/batch-service/*** ✅ - используется
10. **.claude/*** ✅ - AI configuration

### Подтверждение удаления

Перед удалением рекомендую:
1. ✅ **git commit** текущего состояния
2. ✅ **Создать тег** `before-docs-cleanup`
3. ✅ **Запустить Architect** для review списка
4. ✅ **Получить подтверждение пользователя**

---

## 📈 Результат после удаления

### Было:
- 71 файл
- ~900KB
- 79% неактуальных/избыточных

### Станет:
- **49 файлов** (-31%)
- **~430KB** (-52%)
- **30% актуальные**

### После архивирования и консолидации:
- **~35 файлов** (-51%)
- **~300KB** (-67%)
- **70% актуальные**

---

**Следующий шаг:** Получить подтверждение на удаление installation-service и других файлов?

**Версия:** 1.0
**Автор:** AI Orchestrator
**Дата:** 2025-10-31
