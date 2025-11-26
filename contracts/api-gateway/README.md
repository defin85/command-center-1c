# API Gateway OpenAPI Contract

> OpenAPI 3.0.3 спецификация для публичного API CommandCenter1C (Frontend → API Gateway)

---

## О

API Gateway - единая точка входа для Frontend приложения. Выполняет функции:
- **JWT аутентификация** - проверка токенов для защищенных endpoints
- **Rate limiting** - ограничение 100 запросов/минуту на пользователя
- **Proxy к Orchestrator** - большинство запросов проксируются в Django
- **CORS handling** - обработка кросс-доменных запросов

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│ Frontend (React + TypeScript)                           │
│  • Использует автогенерированный TypeScript клиент      │
│  • Type-safe API calls с автодополнением IDE            │
└──────────────────┬──────────────────────────────────────┘
                   ↓ HTTP/HTTPS (Bearer JWT)
┌──────────────────┴──────────────────────────────────────┐
│ API Gateway (Go:8080)                                   │
│  • JWT auth + Rate limiting                             │
│  • ProxyToOrchestrator для бизнес-логики                │
│  • Собственные endpoints: /health, /metrics             │
└──────────────────┬──────────────────────────────────────┘
                   ↓ HTTP (internal)
┌──────────────────┴──────────────────────────────────────┐
│ Orchestrator (Django:8000) + Микросервисы               │
└─────────────────────────────────────────────────────────┘
```

## Endpoints

### Собственные (не прокси)

**Health & Status:**
- `GET /health` - health check API Gateway
- `GET /metrics` - Prometheus метрики
- `GET /api/v1/public/status` - публичный статус системы (без auth)

### Проксируемые (→ Orchestrator)

**Operations:**
- `GET /api/v1/operations` - список операций
- `GET /api/v1/operations/:id` - детали операции
- `POST /api/v1/operations/:id/cancel` - отмена операции

**Databases:**
- `GET /api/v1/databases` - список баз 1С
- `GET /api/v1/databases/:id` - детали базы
- `GET /api/v1/databases/:id/health` - health check базы

**Clusters:**
- `GET /api/v1/databases/clusters` - список кластеров
- `POST /api/v1/databases/clusters` - создать кластер
- `POST /api/v1/databases/clusters/:id/sync` - синхронизировать базы из RAS

**Extensions:**
- `GET /api/v1/extensions/storage` - список загруженных расширений

Полный список см. в `openapi.yaml`.

## Автоматическая генерация TypeScript клиента

### Что генерируется

**Output директория:** `frontend/src/api/generated/`

**Содержимое:**
```
frontend/src/api/generated/
├── api.ts              # API классы (DefaultApi)
├── base.ts             # Базовые HTTP конфигурации
├── common.ts           # Общие утилиты
├── configuration.ts    # Configuration класс
└── index.ts            # Re-exports
```

### Как использовать

**1. Сгенерировать клиент:**
```bash
# Автоматически при старте проекта
./scripts/dev/start-all.sh

# Или вручную
./contracts/scripts/generate-all.sh --force
```

**2. Импортировать в React:**
```typescript
import { DefaultApi, Configuration } from '@/api/generated';

// Создать API client с конфигурацией
const config = new Configuration({
  basePath: 'http://localhost:8080',
  accessToken: localStorage.getItem('jwt_token') || undefined
});

const api = new DefaultApi(config);

// Type-safe API calls
const operations = await api.listOperations();
const database = await api.getDatabase('uuid-here');
```

**3. Примеры интеграции см. в `EXAMPLE_USAGE.md`**

## Обновление API

### Workflow при изменении endpoints

1. **Обновить OpenAPI спецификацию**
   ```bash
   # Редактировать
   vim contracts/api-gateway/openapi.yaml

   # Валидировать
   ./contracts/scripts/validate-specs.sh
   ```

2. **Проверить breaking changes**
   ```bash
   ./contracts/scripts/check-breaking-changes.sh
   ```

3. **Регенерировать TypeScript клиент**
   ```bash
   ./contracts/scripts/generate-all.sh --force
   ```

4. **Обновить Frontend код**
   - Компилятор TypeScript покажет несовместимости
   - Обновить компоненты под новые типы

5. **Commit изменения**
   ```bash
   git add contracts/api-gateway/openapi.yaml
   git add frontend/src/api/generated/
   git commit -m "feat(api): update operations endpoint"
   ```

### Добавление нового endpoint

**Пример: добавить `POST /api/v1/operations`**

```yaml
paths:
  /api/v1/operations:
    post:
      summary: Create new operation
      operationId: createOperation
      tags:
        - operations
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OperationCreate'
      responses:
        '201':
          description: Operation created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Operation'

components:
  schemas:
    OperationCreate:
      type: object
      required:
        - operation_type
        - databases
      properties:
        operation_type:
          type: string
          enum: [install_extension, update_data]
        databases:
          type: array
          items:
            type: string
            format: uuid
```

**После сохранения:**
1. Валидация пройдет автоматически (pre-commit hook)
2. TypeScript клиент регенерируется автоматически
3. Новый метод `api.createOperation()` станет доступен в Frontend

## Versioning

### Текущая версия: v1

Все endpoints начинаются с `/api/v1/`.

### Breaking changes

**При breaking change:**
1. Создать новую версию API: `/api/v2/`
2. Поддерживать обе версии параллельно (grace period)
3. Добавить deprecation warnings в v1
4. Документировать migration guide

**Пример breaking change:**
- Изменение типа поля (string → integer)
- Удаление обязательного поля
- Изменение enum значений
- Изменение формата response

## Security

### JWT Authentication

**Все protected endpoints требуют JWT токен:**

```typescript
// В configuration
const config = new Configuration({
  basePath: 'http://localhost:8080',
  accessToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
});
```

**HTTP заголовок:**
```
Authorization: Bearer <jwt_token>
```

### Rate Limiting

**Лимит:** 100 запросов/минуту на пользователя

**При превышении:**
- HTTP Status: `429 Too Many Requests`
- Response:
  ```json
  {
    "error": "Rate limit exceeded",
    "code": "RATE_LIMIT"
  }
  ```

## Troubleshooting

### TypeScript клиент не генерируется

**Проблема:** `openapi-generator-cli not found`

**Решение:**
```bash
# Установить глобально
npm install -g @openapitools/openapi-generator-cli

# Или использовать npx (без установки)
npx @openapitools/openapi-generator-cli --version
```

### Ошибки компиляции TypeScript после обновления

**Причина:** Breaking changes в API

**Решение:**
1. Проверить changelog: `git diff HEAD~1 contracts/api-gateway/openapi.yaml`
2. Обновить типы в компонентах React
3. Использовать автодополнение IDE для новых типов

### OpenAPI спецификация не проходит валидацию

**Проверить:**
```bash
./contracts/scripts/validate-specs.sh
```

**Частые ошибки:**
- Отсутствует `operationId` (обязателен для каждого endpoint)
- Неправильный `$ref` путь
- Дублирование operationId
- Невалидный YAML синтаксис

## См. также

- [OpenAPI 3.0 Specification](https://spec.openapis.org/oas/v3.0.3)
- [EXAMPLE_USAGE.md](./EXAMPLE_USAGE.md) - примеры использования
- [../../README.md](../../README.md) - общая документация проекта
- [../README.md](../README.md) - Contract-First подход

---

**Дата создания:** 2025-11-24
**Версия спецификации:** 1.0.0
**Статус:** ✅ Production Ready
