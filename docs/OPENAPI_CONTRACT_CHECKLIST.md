# OpenAPI Contract-First Чек-лист

Быстрая справка для работы с OpenAPI контрактами в проекте CommandCenter1C.

---

## Быстрый старт

### 1. Установка git hooks (первый раз)

```bash
git config core.hooksPath .githooks
```

**Проверка установки:**
```bash
git config core.hooksPath
# Должно вывести: .githooks
```

---

### 2. Workflow разработки

#### Когда нужно обновить API спецификацию:

1. **Отредактировать спецификацию**
   ```bash
   # Отредактировать файл:
   contracts/ras-adapter/openapi.yaml
   ```

2. **Валидировать изменения** (обязательно ПЕРЕД коммитом)
   ```bash
   ./contracts/scripts/validate-specs.sh
   ```
   Должно быть: `✓ All specifications are valid`

3. **Сгенерировать новые типы**
   ```bash
   ./contracts/scripts/generate-all.sh
   ```
   Будут обновлены:
   - `go-services/ras-adapter/internal/api/generated/server.go`
   - `orchestrator/apps/databases/clients/generated/ras_adapter_api_client/`

4. **Коммитить**
   ```bash
   git add contracts/ras-adapter/openapi.yaml
   git add go-services/ras-adapter/internal/api/generated/
   git add orchestrator/apps/databases/clients/generated/
   git commit -m "fix: Update ras-adapter API spec - add new field"
   ```

   **Важно:** Git hook автоматически:
   - Валидирует спецификацию
   - Проверяет breaking changes
   - Регенерирует клиентов
   - Добавляет сгенерированные файлы в коммит

---

## Общие команды

### Валидировать спецификацию

```bash
./contracts/scripts/validate-specs.sh
```

**Результаты:**
- ✓ Valid → OK
- ✗ Invalid → ошибка синтаксиса YAML или OpenAPI

### Сгенерировать клиентов

```bash
# Нормальная генерация (пропускает неизмененные)
./contracts/scripts/generate-all.sh

# Принудительная регенерация
./contracts/scripts/generate-all.sh --force
```

### Проверить breaking changes

```bash
./contracts/scripts/check-breaking-changes.sh
```

---

## Использование сгенерированного кода

### Go (server types)

**Импорт в ras-adapter:**
```go
import "github.com/commandcenter1c/commandcenter/go-services/ras-adapter/internal/api/generated"

func GetInfobases(c *gin.Context, clusterId string) {
    // Типы автоматически доступны:
    response := generated.InfobasesResponse{
        Infobases: []generated.Infobase{},
    }
}
```

### Python (client)

**Импорт в Orchestrator:**
```python
from apps.databases.clients.generated.ras_adapter_api_client import Client
from apps.databases.clients.generated.ras_adapter_api_client.api.infobases import (
    get_infobases,
    create_infobase,
)
from apps.databases.clients.generated.ras_adapter_api_client.models import (
    CreateInfobaseRequest,
    Infobase,
)

# Использование
client = Client(base_url="http://ras-adapter:8088")
infobases = await get_infobases(
    client=client,
    cluster_id="uuid-here"
)
```

---

## Структура контрактов

```
contracts/
├── README.md                          # Основная документация
├── ras-adapter/
│   ├── openapi.yaml                   # OpenAPI 3.0 спецификация
│   └── EXAMPLE_USAGE.md               # Примеры использования
├── api-gateway/                       # (в разработке)
├── scripts/
│   ├── validate-specs.sh              # Валидация
│   ├── generate-all.sh                # Генерация клиентов
│   └── check-breaking-changes.sh      # Проверка breaking changes
└── .githooks/
    ├── pre-commit                     # Git hook для валидации
    └── README.md                      # Инструкции установки
```

---

## Важные параметры API

### Для инфобаз (infobases endpoints)

**ИСПОЛЬЗУЙТЕ:** `cluster_id`

```yaml
# Правильно:
GET /api/v2/list-infobases?cluster_id=<uuid>
```

### Для кластеров (clusters endpoints)

**ИСПОЛЬЗУЙТЕ:** `server`

```yaml
# Правильно:
GET /api/v2/list-clusters?server=localhost:1545
GET /api/v2/get-cluster?cluster_id=<uuid>&server=localhost:1545
```

---

## Troubleshooting

### Ошибка валидации: "Invalid OpenAPI spec"

1. Проверьте YAML синтаксис:
   ```bash
   ./contracts/scripts/validate-specs.sh
   ```

2. Ошибка будет указывать строку и причину

3. Исправьте и повторите

### Git hook не запускается

```bash
# Проверьте установку:
git config core.hooksPath

# Если пусто, установите:
git config core.hooksPath .githooks

# Проверьте права:
chmod +x .githooks/pre-commit
```

### Breaking changes при коммите

**Варианты:**
1. **Обновить версию API** (v1 → v2)
2. **Добавить deprecation notices** в спецификацию
3. **Создать migration guide** для клиентов

Затем подтвердить коммит при запросе hook.

### Сгенерированный код не импортируется (Python)

```bash
# Убедитесь что сгенерировано:
ls orchestrator/apps/databases/clients/generated/ras_adapter_api_client/

# Проверьте __init__.py:
cat orchestrator/apps/databases/clients/generated/__init__.py

# Попробуйте принудительную регенерацию:
./contracts/scripts/generate-all.sh --force
```

---

## Производительность

| Операция | Время |
|----------|-------|
| Валидация | ~50ms |
| Первая генерация | ~100ms |
| Генерация со скипом | ~114ms |
| Force регенерация | ~150ms |

> Скрипты оптимизированы: пропускают неизмененные файлы

---

## Интеграция в dev workflow

### При запуске `./scripts/dev/start-all.sh`

**Phase 1.5** автоматически:
1. Валидирует спецификации
2. Генерирует Go типы
3. Генерирует Python клиент
4. Выводит путиков сгенерированным файлам

### При коммите

**Pre-commit hook** автоматически:
1. Валидирует измененные спецификации
2. Проверяет breaking changes
3. Регенерирует клиентов
4. Добавляет сгенерированные файлы в коммит

---

## Полная документация

- **Основное руководство:** `contracts/README.md`
- **Примеры кода:** `contracts/ras-adapter/EXAMPLE_USAGE.md`
- **Инструкции git hooks:** `.githooks/README.md`
- **Проектный контекст:** `CLAUDE.md` (секция OPENAPI CONTRACTS)
- **Тестовый отчет:** `OPENAPI_CONTRACT_TESTING_REPORT.md`

---

## Поддерживаемые сервисы

- **ras-adapter** ✅ Полностью поддерживается
  - OpenAPI спецификация: `contracts/ras-adapter/openapi.yaml`
  - Go типы: `go-services/ras-adapter/internal/api/generated/`
  - Python клиент: `orchestrator/apps/databases/clients/generated/`

- **api-gateway** 🔄 В разработке
- **worker** 🔄 В разработке

---

**Версия:** 1.0
**Обновлено:** 2025-11-24
**Статус:** Готово к использованию
