# OpenAPI Contracts - API First Development

Этот проект использует **Contract-First подход** для разработки микросервисов: OpenAPI спецификации являются единым источником правды для REST API контрактов между сервисами.

## Зачем Contract-First?

**Проблема, которую решаем:**
- Рассинхронизация между клиентами и серверами
- Ошибки параметров (например, `cluster` vs `cluster_id`)
- Отсутствие автоматической валидации изменений API
- Ручное поддержание consistency между сервисами

**Решение:**
1. OpenAPI спецификация как **единый источник правды**
2. Автоматическая генерация типов и клиентов
3. Валидация breaking changes до коммита
4. Встроенная документация (Swagger UI)

## Структура

```
contracts/
├── README.md                       # Этот файл
├── orchestrator/
│   ├── openapi.yaml                # Generated bundle (delivery artifact)
│   └── src/                        # Editable source-of-truth
│       ├── openapi.yaml            # Root modular OpenAPI file
│       ├── paths/                  # PathItem modules
│       └── components/             # Reusable components
│           └── schemas/
├── orchestrator-internal/
│   └── openapi.yaml                # Internal API для Go Worker <-> Django
├── api-gateway/                    # (будущее)
│   └── openapi.yaml
├── worker/                         # (будущее)
│   └── openapi.yaml
└── scripts/
    ├── build-orchestrator-openapi.sh # Build/check orchestrator bundle
    ├── generate-all.sh             # Генерация всех клиентов
    ├── validate-specs.sh           # Валидация спецификаций
    └── check-breaking-changes.sh   # Проверка breaking changes
```

## Workflow: Как добавить новый endpoint

### Шаг 1: Обновить modular source

Для orchestrator редактируйте только `contracts/orchestrator/src/**`:

```bash
# PathItem модули
vim contracts/orchestrator/src/paths/<path-module>.yaml

# Schema модули (если нужен новый schema)
vim contracts/orchestrator/src/components/schemas/<SchemaName>.yaml
```

Пример path-модуля:

```yaml
get:
  summary: My new endpoint
  operationId: getMyEndpoint
  tags:
    - v2
  responses:
    '200':
      description: Success
      content:
        application/json:
          schema:
            $ref: '../components/schemas/MyResponse.yaml'
```

**ВАЖНО:**
- Всегда используйте `operationId` (уникальный идентификатор)
- Используйте `snake_case` для параметров (соответствие с Go/Python)
- Добавляйте описания (`description`) для документации
- Переиспользуйте схемы через `$ref`

Соглашения по именованию и размещению модулей описаны в `contracts/orchestrator/src/README.md`.

### Шаг 2: Собрать bundle и проверить актуальность

```bash
./contracts/scripts/build-orchestrator-openapi.sh build
./contracts/scripts/build-orchestrator-openapi.sh check
```

Файл `contracts/orchestrator/openapi.yaml` является generated артефактом. Не редактируйте его вручную.

### Шаг 3: Валидация

```bash
./contracts/scripts/validate-specs.sh
```

### Шаг 4: Генерация кода

Сгенерируйте маршруты/клиенты:

```bash
./contracts/scripts/generate-all.sh
```

Это создаст:
- **Go:** `go-services/<service>/internal/api/generated/server.go`
- **Python:** `orchestrator/apps/databases/clients/generated/<service>_api_client/`

### Шаг 5: Реализация

**Go (server):**

Существующие handlers в `internal/api/rest/` должны использовать сгенерированные типы:

```go
import "github.com/commandcenter1c/commandcenter/<service>/internal/api/generated"

func MyHandler(svc *service.MyService) gin.HandlerFunc {
    return func(c *gin.Context) {
        // Используйте сгенерированные типы
        var req generated.MyRequest
        if err := c.ShouldBindJSON(&req); err != nil {
            c.JSON(400, gin.H{"error": err.Error()})
            return
        }
        // ...
    }
}
```

**Python (client):**

Используйте сгенерированный клиент:

```python
from apps.databases.clients.generated.ras_adapter_api_client import Client
from apps.databases.clients.generated.ras_adapter_api_client.api.infobases import get_infobases

client = Client(base_url="http://localhost:8088")
response = get_infobases.sync_detailed(
    client=client,
    cluster_id="uuid-here"
)

if response.status_code == 200:
    infobases = response.parsed.infobases
```

### Шаг 6: Коммит

При коммите автоматически запустится:
1. Валидация OpenAPI спецификаций
2. Проверка breaking changes
3. Регенерация клиентов

```bash
git add contracts/orchestrator/src/
git add contracts/orchestrator/openapi.yaml
git add go-services/api-gateway/internal/routes/generated/
git add frontend/src/api/generated/
git commit -m "feat(api): Add new endpoint"
# Pre-commit hook выполнит все проверки
```

## Workflow: Изменение существующего endpoint

### Backward-compatible изменения (✅ безопасно)

- Добавление новых **опциональных** параметров
- Добавление новых полей в ответ
- Добавление новых endpoints
- Улучшение описаний/документации

### Breaking changes (⚠️ требуют внимания)

- Изменение типа параметра
- Переименование параметра/поля
- Удаление параметра/endpoint
- Изменение обязательности (optional → required)

**Процесс при breaking changes:**

1. Создайте новую версию API (например, `/api/v2/...`)
2. Добавьте deprecation notice в старый endpoint:
   ```yaml
   deprecated: true
   description: |
     DEPRECATED: Use /api/v2/endpoint instead.
     This endpoint will be removed in version 3.0.
   ```
3. Обновите документацию с migration guide
4. Дайте клиентам время на миграцию (минимум 1-2 спринта)

## Инструменты

### Установка зависимостей

**Go:**
```bash
go install github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@latest
```

**Python:**
```bash
cd orchestrator
source venv/Scripts/activate
pip install openapi-python-client
```

**Опционально (для расширенных проверок):**
```bash
# Orchestrator modular bundle
npx --yes @redocly/cli@2.19.1 --version

# Breaking changes detection
go install github.com/oasdiff/oasdiff@latest

# OpenAPI validation
npm install -g @apidevtools/swagger-cli
```

### Активация Git Hooks

Для автоматической валидации при коммите:

```bash
git config core.hooksPath .githooks
```

См. [.githooks/README.md](../.githooks/README.md) для деталей.

## Генерация клиентов

### Автоматическая (рекомендуется)

Запускается автоматически при `./scripts/dev/start-all.sh`:

```bash
./scripts/dev/start-all.sh
# Phase 1.5: Генерация API клиентов из OpenAPI
```

### Ручная

```bash
# Build/check orchestrator bundle from modular source
./contracts/scripts/build-orchestrator-openapi.sh build
./contracts/scripts/build-orchestrator-openapi.sh check

# Все сервисы
./contracts/scripts/generate-all.sh

# С принудительной регенерацией
./contracts/scripts/generate-all.sh --force
```

## Валидация

### Перед коммитом

```bash
./contracts/scripts/validate-specs.sh
```

### Проверка breaking changes

```bash
# Сравнить с HEAD~1
./contracts/scripts/check-breaking-changes.sh

# Сравнить с конкретным коммитом
./contracts/scripts/check-breaking-changes.sh abc123
```

## Best Practices

### 1. Naming Conventions

- **Параметры:** `snake_case` (cluster_id, infobase_id)
- **Схемы:** `PascalCase` (ClusterInfo, InfobaseResponse)
- **operationId:** `camelCase` (getInfobases, createCluster)

### 2. Версионирование

- Используйте семантическое версионирование для API
- Major bump при breaking changes
- Minor bump при новых features
- Patch bump при bug fixes

### 3. Документация

- Всегда добавляйте `description` для endpoints и параметров
- Используйте `example` для типичных значений
- Документируйте error responses

### 4. Переиспользование

- Используйте `$ref` для общих схем
- Создавайте reusable `components/schemas`
- Группируйте связанные endpoints по `tags`

### 5. Security

- Документируйте требования аутентификации
- Используйте `securitySchemes` для OAuth/JWT
- Валидируйте входные данные на уровне OpenAPI схемы

## Troubleshooting

### Ошибка "bundle is out of date"

```
Error: bundle is out of date: contracts/orchestrator/openapi.yaml
```

**Решение:**
```bash
./contracts/scripts/build-orchestrator-openapi.sh build
```

Если ошибка повторяется, проверьте изменения в `contracts/orchestrator/src/**` и повторите `build`.

### Ошибка генерации Go кода

```
error parsing configuration...
```

**Решение:** Проверьте формат `.oapi-codegen.yaml` (должен соответствовать v2 API)

### Ошибка генерации Python клиента

```
Error parsing OpenAPI spec
```

**Решение:**
1. Проверьте синтаксис YAML
2. Запустите `./contracts/scripts/validate-specs.sh`
3. Убедитесь, что используете OpenAPI 3.0.x (не 3.1)

### Breaking changes не детектируются

**Решение:** Установите `oasdiff`:

```bash
go install github.com/oasdiff/oasdiff@latest
```

В CI отсутствие `oasdiff` является блокирующей ошибкой.

### В CI падает валидация из-за "no OpenAPI validators available"

**Причина:** в CI отключён fallback на YAML-синтаксис без полноценного OpenAPI validator.

**Решение:**
1. Установите `oapi-codegen` или `swagger-cli`.
2. Повторите `./contracts/scripts/validate-specs.sh`.

### Git hook не запускается

**Решение:**

```bash
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
```

## Примеры

### Добавление нового endpoint

- Source modules: `contracts/orchestrator/src/**`
- Bundled contract: `contracts/orchestrator/openapi.yaml`

### Использование сгенерированных типов

**Go:**
```go
// internal/api/rest/my_handler.go
import "github.com/.../internal/api/generated"

response := generated.SuccessResponse{
    Success: true,
    Message: "Operation completed",
}
c.JSON(200, response)
```

## Дальнейшее развитие

- [ ] Добавить OpenAPI specs для `api-gateway`
- [ ] Добавить OpenAPI specs для `worker`
- [ ] Настроить CI/CD валидацию
- [ ] Интегрировать Swagger UI в API Gateway
- [ ] Автоматическая генерация changelog из breaking changes

## Ссылки

- [OpenAPI 3.0 Specification](https://swagger.io/specification/)
- [oapi-codegen Documentation](https://github.com/oapi-codegen/oapi-codegen)
- [openapi-python-client](https://github.com/openapi-generators/openapi-python-client)
- [API Versioning Best Practices](https://www.troyhunt.com/your-api-versioning-is-wrong-which-is/)
