# Примеры использования сгенерированного API клиента

## Python (Django)

### Базовая настройка

```python
from apps.databases.clients.generated.ras_adapter_api_client import Client
from apps.databases.clients.generated.ras_adapter_api_client.api.infobases import (
    get_infobases,
    get_infobase_by_id,
    lock_infobase,
    unlock_infobase,
)
from apps.databases.clients.generated.ras_adapter_api_client.models import (
    LockInfobaseRequest,
    UnlockInfobaseRequest,
)

# Создание клиента
client = Client(base_url="http://localhost:8088")
```

### Получение списка баз

```python
# ВАЖНО: Используем cluster_id, а не cluster!
response = get_infobases.sync_detailed(
    client=client,
    cluster_id="550e8400-e29b-41d4-a716-446655440000"
)

if response.status_code == 200:
    infobases_response = response.parsed
    for infobase in infobases_response.infobases:
        print(f"Infobase: {infobase.name} (UUID: {infobase.uuid})")
else:
    print(f"Error: {response.status_code}")
```

### Блокировка базы

```python
request = LockInfobaseRequest(
    cluster_id="550e8400-e29b-41d4-a716-446655440000",
    db_user="admin",
    db_pwd="password"
)

response = lock_infobase.sync_detailed(
    client=client,
    infobase_id="660e8400-e29b-41d4-a716-446655440001",
    json_body=request
)

if response.status_code == 200:
    result = response.parsed
    print(f"Success: {result.message}")
else:
    print(f"Error: {response.status_code}")
```

### Асинхронное использование

```python
import asyncio
from apps.databases.clients.generated.ras_adapter_api_client import Client
from apps.databases.clients.generated.ras_adapter_api_client.api.infobases import get_infobases

async def fetch_infobases(cluster_id: str):
    async with Client(base_url="http://localhost:8088") as client:
        response = await get_infobases.asyncio_detailed(
            client=client,
            cluster_id=cluster_id
        )

        if response.status_code == 200:
            return response.parsed.infobases
        else:
            raise Exception(f"Failed to fetch infobases: {response.status_code}")

# Использование
infobases = asyncio.run(fetch_infobases("550e8400-e29b-41d4-a716-446655440000"))
```

## Go (Server)

### Использование сгенерированных типов

```go
package rest

import (
    "net/http"
    "github.com/commandcenter1c/commandcenter/ras-adapter/internal/api/generated"
    "github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
    "github.com/gin-gonic/gin"
)

// Пример handler, использующий сгенерированные типы
func GetInfobasesHandler(svc *service.InfobaseService) gin.HandlerFunc {
    return func(c *gin.Context) {
        // Параметры из query string
        clusterID := c.Query("cluster_id")

        // Вызов сервиса
        infobases, err := svc.GetInfobases(c.Request.Context(), clusterID)
        if err != nil {
            c.JSON(http.StatusInternalServerError, generated.ErrorResponse{
                Error: err.Error(),
            })
            return
        }

        // Формирование ответа используя сгенерированные типы
        response := generated.InfobasesResponse{
            Infobases: convertToGeneratedInfobases(infobases),
        }

        c.JSON(http.StatusOK, response)
    }
}

// Конвертация из internal models в generated types
func convertToGeneratedInfobases(infobases []models.Infobase) []generated.Infobase {
    result := make([]generated.Infobase, len(infobases))
    for i, ib := range infobases {
        result[i] = generated.Infobase{
            Uuid:              ib.UUID,
            Name:              ib.Name,
            Dbms:              ib.DBMS,
            DbServer:          ib.DBServer,
            DbName:            ib.DBName,
            ScheduledJobsDeny: ib.ScheduledJobsDeny,
            SessionsDeny:      ib.SessionsDeny,
        }
    }
    return result
}
```

## Обработка ошибок

### Python

```python
from apps.databases.clients.generated.ras_adapter_api_client.errors import UnexpectedStatus

try:
    response = get_infobases.sync_detailed(
        client=client,
        cluster_id="invalid-uuid"
    )

    if response.status_code == 400:
        error = response.parsed
        print(f"Bad Request: {error.error}")
    elif response.status_code == 500:
        error = response.parsed
        print(f"Server Error: {error.error}")
    else:
        infobases = response.parsed.infobases

except UnexpectedStatus as e:
    print(f"Unexpected error: {e}")
```

### Go

```go
// Обработка различных статусов
if err != nil {
    c.JSON(http.StatusInternalServerError, generated.ErrorResponse{
        Error: fmt.Sprintf("Internal error: %v", err),
    })
    return
}

// Валидация параметров
if clusterID == "" {
    c.JSON(http.StatusBadRequest, generated.ErrorResponse{
        Error: "cluster_id parameter is required",
    })
    return
}

// Успешный ответ
c.JSON(http.StatusOK, generated.SuccessResponse{
    Success: true,
    Message: "Operation completed successfully",
})
```

## Миграция с старого кода

### До (старый код)

```python
# Проблема: использовался параметр "cluster" вместо "cluster_id"
import requests

response = requests.get(
    "http://localhost:8088/api/v2/list-infobases",
    params={"cluster": cluster_uuid}  # НЕПРАВИЛЬНО!
)
```

### После (с OpenAPI клиентом)

```python
# Решение: типизированный клиент гарантирует правильные параметры
from apps.databases.clients.generated.ras_adapter_api_client import Client
from apps.databases.clients.generated.ras_adapter_api_client.api.infobases import get_infobases

client = Client(base_url="http://localhost:8088")
response = get_infobases.sync_detailed(
    client=client,
    cluster_id=cluster_uuid  # ПРАВИЛЬНО! Компилятор/IDE подскажет
)
```

## Преимущества

1. **Типизация:** IDE автодополнение для всех параметров и полей
2. **Валидация:** Ошибки параметров детектируются на этапе написания кода
3. **Документация:** Встроенные docstrings из OpenAPI спецификации
4. **Consistency:** Гарантия соответствия клиента и сервера
5. **Автогенерация:** Обновляется автоматически при изменении API

## Troubleshooting

### Ошибка "cluster_id parameter is required"

**Проблема:** Старый код использует параметр `cluster` вместо `cluster_id`.

**Решение:** Обновите код, используя сгенерированный клиент:
```python
# Неправильно
requests.get(..., params={"cluster": uuid})

# Правильно
get_infobases.sync_detailed(client=client, cluster_id=uuid)
```

### Ошибка импорта Python клиента

**Проблема:** `ModuleNotFoundError: No module named 'ras_adapter_api_client'`

**Решение:**
```bash
cd /c/1CProject/command-center-1c
./contracts/scripts/generate-all.sh --force
```

### Go compilation error: "undefined: generated"

**Проблема:** Сгенерированные типы не найдены.

**Решение:**
```bash
cd /c/1CProject/command-center-1c
./contracts/scripts/generate-all.sh --force
cd go-services/ras-adapter && go mod tidy
```
