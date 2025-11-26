# Быстрый старт: OpenAPI Contract-First

**Время прочтения:** 5 минут

---

## Для разработчиков

### Первый раз (одноразово)

```bash
# Активировать git hooks
git config core.hooksPath .githooks

# Готово!
```

### Работа с API

```bash
# 1. Обновить спецификацию
vim contracts/ras-adapter/openapi.yaml

# 2. Проверить синтаксис
./contracts/scripts/validate-specs.sh
# Результат: ✓ All specifications are valid

# 3. Сгенерировать типы
./contracts/scripts/generate-all.sh
# Результат: ✓ Go server types generated, ✓ Python client generated

# 4. Обновить код (Go / Python)
# Типы автоматически доступны в:
# - go-services/ras-adapter/internal/api/generated/server.go
# - orchestrator/apps/databases/clients/generated/ras_adapter_api_client/

# 5. Коммитить
git add contracts/ras-adapter/openapi.yaml
git add go-services/ras-adapter/internal/api/generated/
git add orchestrator/apps/databases/clients/generated/
git commit -m "feat: Add new endpoint"
# Git hook автоматически валидирует и регенерирует!
```

---

## Примеры кода

### Go (в ras-adapter)

```go
import "github.com/commandcenter1c/commandcenter/go-services/ras-adapter/internal/api/generated"

func GetInfobases(c *gin.Context, clusterId string) {
    response := generated.InfobasesResponse{
        Infobases: []generated.Infobase{
            {
                Name: "my-db",
                UUID: "uuid-123",
            },
        },
    }
    c.JSON(200, response)
}
```

### Python (в Orchestrator)

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
async def list_infobases():
    client = Client(base_url="http://ras-adapter:8088")
    infobases = await get_infobases(
        client=client,
        cluster_id="uuid-123"
    )
    return infobases
```

---

## Основные команды

```bash
# Валидировать спецификацию
./contracts/scripts/validate-specs.sh

# Сгенерировать клиентов
./contracts/scripts/generate-all.sh

# Принудительная регенерация
./contracts/scripts/generate-all.sh --force

# Проверить breaking changes
./contracts/scripts/check-breaking-changes.sh

# Полный dev workflow
./scripts/dev/start-all.sh  # Phase 1.5 запустится автоматически
```

---

## Параметры API

**ПРАВИЛЬНО:**
```
GET /api/v1/infobases?cluster_id=<uuid>
```

**НЕПРАВИЛЬНО:**
```
GET /api/v1/infobases?cluster=<uuid>  // ❌ deprecated
```

---

## Когда что-то не работает

| Проблема | Решение |
|----------|---------|
| Git hook не запускается | `git config core.hooksPath .githooks` |
| Ошибка валидации | `./contracts/scripts/validate-specs.sh` (см. ошибку) |
| Python не импортируется | `./contracts/scripts/generate-all.sh --force` |
| Go не компилируется | `cd go-services/ras-adapter && go build ./cmd` |

---

## Файлы для справки

- **Быстрая справка:** `docs/OPENAPI_CONTRACT_CHECKLIST.md`
- **Полный отчет:** `OPENAPI_CONTRACT_TESTING_REPORT.md`
- **Примеры:** `contracts/ras-adapter/EXAMPLE_USAGE.md`
- **Инструкции:** `NEXT_STEPS_AFTER_TESTING.md`

---

## Тестирование

```bash
# Проверить валидность спецификации
./contracts/scripts/validate-specs.sh
# ✓ All specifications are valid

# Сгенерировать и скомпилировать
./contracts/scripts/generate-all.sh
cd go-services/ras-adapter && go build ./cmd
# OK - компилируется без ошибок

# Проверить Python клиент
cd orchestrator && python -c "from apps.databases.clients.generated.ras_adapter_api_client import Client; print('OK')"
# OK - импортируется успешно
```

---

**Все готово к использованию!** ✅

Полная документация в [`TESTING_RESULTS.md`](./TESTING_RESULTS.md)
