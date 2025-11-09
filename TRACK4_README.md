# Track 4: Batch Service - Advanced Features

> **Sprint 4 (опционально)** - Продвинутый функционал для batch-service

---

## 📍 Цель Track 4

Реализовать продвинутые функции управления расширениями 1С:
- **Storage** - Централизованное хранилище .cfe файлов
- **Metadata extraction** - Извлечение метаданных из расширений
- **Session termination** - Интеграция с cluster-service для завершения сеансов
- **Rollback** - Механизм отката установленных расширений

---

## 🎯 Задачи Sprint 4

### [P3.1] Хранилище расширений (8 часов)

**Endpoints:**
- `POST /api/v1/extensions/upload` - Загрузка .cfe файла
- `GET /api/v1/extensions/storage` - Список файлов в хранилище
- `DELETE /api/v1/extensions/storage/{name}` - Удаление файла из хранилища

**Функции:**
```
- Upload .cfe через API
- Версионирование файлов (name_v1.0.0.cfe)
- Валидация формата файла
- Cleanup старых версий (retention policy)
- Metadata хранение (размер, дата загрузки, автор)
```

**Acceptance criteria:**
- ✅ Можно загрузить .cfe через curl/Postman
- ✅ Файлы сохраняются в структурированном виде
- ✅ Версионирование работает корректно
- ✅ Cleanup удаляет старые версии (keep last 3)

---

### [P3.2] Metadata extraction (12 часов)

**Endpoints:**
- `GET /api/v1/extensions/{file}/metadata` - Извлечь метаданные из .cfe

**Извлекаемые данные:**
```json
{
  "name": "ODataAutoConfig",
  "version": "1.0.5",
  "author": "Разработчик",
  "description": "Автоконфигурация OData",
  "platform_version_min": "8.3.20.0",
  "platform_version_max": "8.3.27.9999",
  "dependencies": ["CoreExtension"],
  "size_bytes": 1024000,
  "modification_date": "2025-11-08T12:00:00Z",
  "checksum_md5": "abc123...",
  "objects_count": {
    "catalogs": 5,
    "documents": 3,
    "reports": 2
  }
}
```

**Технические подходы:**
- **Вариант 1:** Парсинг XML внутри .cfe (расширение это zip-архив)
- **Вариант 2:** Через COM-connection к 1С
- **Вариант 3:** Через ConfigurationRepositoryReport

**Acceptance criteria:**
- ✅ Извлечение базовых метаданных (name, version)
- ✅ Извлечение зависимостей расширения
- ✅ Подсчет объектов конфигурации
- ✅ Валидация совместимости с версией платформы

---

### [P3.3] Session termination integration (6 часов)

**Проблема:** Активные сеансы блокируют установку расширений

**Решение:** Интеграция с cluster-service для автоматического завершения сеансов

**Flow:**
```
1. Django → batch-service: InstallExtension
2. batch-service → cluster-service: GET /sessions (для данной базы)
3. Если сеансы есть:
   - batch-service → cluster-service: POST /sessions/terminate
   - Ожидание 5-10 секунд
4. batch-service → 1cv8.exe: Установка расширения
5. Результат → Django
```

**Endpoints cluster-service:**
- `GET /api/v1/sessions?infobase_id={uuid}` - Получить список сеансов
- `POST /api/v1/sessions/terminate` - Завершить сеансы

**Acceptance criteria:**
- ✅ Автоматическое завершение сеансов перед установкой
- ✅ Опция force_terminate (default: false)
- ✅ Обработка ошибок (сеансы не завершились)
- ✅ Логирование terminated sessions

---

### [P3.4] Rollback механизм (10 часов)

**Проблема:** При ошибке установки нет способа откатить изменения

**Решение:** Backup + Restore mechanism

**Flow:**
```
Install Extension:
1. Создать backup текущего расширения (если существует)
   - 1cv8.exe DESIGNER /DumpCfg backup.cfe -Extension Name
2. Установить новое расширение
3. Если ошибка:
   - Restore из backup
   - 1cv8.exe DESIGNER /LoadCfg backup.cfe -Extension Name
4. Если успех:
   - Удалить backup (или сохранить для rollback вручную)
```

**API endpoints:**
- `POST /api/v1/extensions/rollback` - Откат к предыдущей версии
- `GET /api/v1/extensions/backups` - Список доступных backup'ов

**Storage структура:**
```
backups/
├── database_uuid1/
│   ├── ExtensionName_2025-11-08_14-30-00.cfe
│   ├── ExtensionName_2025-11-07_10-15-00.cfe
│   └── ExtensionName.current -> ExtensionName_2025-11-08_14-30-00.cfe
└── database_uuid2/
    └── ...
```

**Acceptance criteria:**
- ✅ Автоматический backup перед каждой установкой
- ✅ Rollback к предыдущей версии через API
- ✅ Retention policy (keep last 5 backups)
- ✅ Cleanup старых backup'ов
- ✅ Метаданные backup'ов (дата, размер, причина создания)

---

## 📊 Оценка времени

| Задача | Приоритет | Время | Зависимости |
|--------|-----------|-------|-------------|
| Extension storage | P3 | 8ч | - |
| Metadata extraction | P3 | 12ч | Storage (для тестирования) |
| Session termination | P3 | 6ч | cluster-service готов |
| Rollback механизм | P3 | 10ч | Storage |

**Итого:** ~36 часов (4-5 дней разработки)

---

## 🚀 Порядок реализации

**День 1-2:** Extension Storage (8ч)
- Создать структуру хранилища
- Реализовать upload endpoint
- Версионирование + cleanup

**День 3-4:** Metadata Extraction (12ч)
- Исследовать формат .cfe
- Парсинг XML метаданных
- API endpoint

**День 5:** Session Termination (6ч)
- HTTP client для cluster-service
- Интеграция в install flow
- Error handling

**День 6-7:** Rollback Mechanism (10ч)
- Backup creation
- Restore logic
- API endpoints

---

## 📂 Структура кода

```
go-services/batch-service/
├── internal/
│   ├── storage/              # ❌ TODO Track 4
│   │   ├── filesystem.go     # Local filesystem storage
│   │   ├── versioning.go     # Версионирование файлов
│   │   └── cleanup.go        # Retention policy
│   ├── metadata/             # ❌ TODO Track 4
│   │   ├── extractor.go      # Извлечение метаданных из .cfe
│   │   └── parser.go         # XML парсинг
│   ├── cluster/              # ❌ TODO Track 4
│   │   └── client.go         # HTTP client для cluster-service
│   └── rollback/             # ❌ TODO Track 4
│       ├── backup.go         # Создание backup'ов
│       ├── restore.go        # Восстановление из backup
│       └── manager.go        # Управление backup'ами
```

---

## 🔗 Связанные документы

- [BATCH_SERVICE_EXTENSIONS_GUIDE.md](../docs/BATCH_SERVICE_EXTENSIONS_GUIDE.md) - Полный план разработки
- [1C_ADMINISTRATION_GUIDE.md](../docs/1C_ADMINISTRATION_GUIDE.md) - RAS/cluster management
- [ROADMAP.md](../docs/ROADMAP.md) - Общий roadmap проекта

---

## ✅ Definition of Done

**Track 4 считается завершенным когда:**

1. ✅ Все 4 задачи реализованы и протестированы
2. ✅ Unit tests coverage > 70%
3. ✅ Integration tests проходят
4. ✅ API endpoints работают через curl/Postman
5. ✅ Документация обновлена
6. ✅ Code review пройден (reviewer agent)
7. ✅ Merge в master без конфликтов

---

## 🛠️ Getting Started

```bash
# Переключиться в worktree track 4
cd C:/1CProject/command-center-1c-track4

# Убедиться что на правильной ветке
git status
# Должно быть: On branch feature/track4-batch-service-advanced-features

# Запустить batch-service
cd go-services/batch-service
go run cmd/main.go

# Тесты
go test ./...
```

---

**Версия:** 1.0
**Создано:** 2025-11-09
**Автор:** Claude (Orchestrator)
**Статус:** 📋 Planning
