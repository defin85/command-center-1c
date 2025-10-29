# Installation Service - Quick Start

## Быстрый запуск

### 1. Проверка конфигурации

Убедитесь, что путь к `rac.exe` правильный в `configs/config.yaml`:

```yaml
rac:
  path: "C:\\Program Files\\1cv8\\8.3.27.1786\\bin\\rac.exe"
```

### 2. Запуск сервиса

```bash
cd go-services/installation-service
go run cmd/main.go
```

Сервис запустится на порту 8085.

### 3. Проверка работоспособности

```bash
# Health check
curl http://localhost:8085/health

# Ожидаемый ответ:
# {"status":"ok","service":"installation-service"}
```

### 4. Получение списка баз

#### Краткий список (быстро)

```bash
curl "http://localhost:8085/api/v1/infobases?server=localhost:1545"
```

**Результат:**
```json
{
  "status": "success",
  "cluster_id": "635eff68-bf69-4e12-a7c9-2967527fc237",
  "cluster_name": "Кластер 1С",
  "total_count": 2,
  "infobases": [
    {
      "uuid": "e1092854-3660-11e7-6b9e-d017c292ea7a",
      "name": "BUH",
      "description": "Бухгалтерия"
    },
    {
      "uuid": "f2193965-4771-11e7-7c0f-e128d383fb8b",
      "name": "TRADE",
      "description": "Торговля"
    }
  ],
  "duration_ms": 850,
  "timestamp": "2025-10-28T12:00:00Z"
}
```

#### Детальный список (медленно)

```bash
curl "http://localhost:8085/api/v1/infobases?server=localhost:1545&detailed=true"
```

**Результат:**
```json
{
  "status": "success",
  "cluster_id": "635eff68-bf69-4e12-a7c9-2967527fc237",
  "cluster_name": "Кластер 1С",
  "total_count": 2,
  "infobases": [
    {
      "uuid": "e1092854-3660-11e7-6b9e-d017c292ea7a",
      "name": "BUH",
      "description": "Бухгалтерия",
      "dbms": "MSSQLServer",
      "db_server": "sql-server\\instance",
      "db_name": "BUH_DB",
      "db_user": "sa",
      "security_level": 0,
      "connection_string": "/S\"server\\BUH\"",
      "locale": "ru"
    }
  ],
  "duration_ms": 3250,
  "timestamp": "2025-10-28T12:00:00Z"
}
```

## Python интеграция

### Простой пример

```python
import requests

# Создать клиент
API_URL = "http://windows-server:8085"

# Получить список баз
response = requests.get(
    f"{API_URL}/api/v1/infobases",
    params={"server": "localhost:1545"}
)

if response.status_code == 200:
    data = response.json()
    print(f"Найдено баз: {data['total_count']}")

    for infobase in data['infobases']:
        print(f"- {infobase['name']}: {infobase['description']}")
else:
    error = response.json()
    print(f"Ошибка: {error['error']} - {error['message']}")
```

### Django интеграция

```python
# settings.py
INSTALLATION_SERVICE_URL = "http://windows-server:8085"

# services/installation_client.py
import requests
from django.conf import settings

class InstallationServiceClient:
    def __init__(self):
        self.base_url = settings.INSTALLATION_SERVICE_URL

    def get_infobases(self, server="localhost:1545", detailed=False):
        """Получить список информационных баз"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/infobases",
                params={
                    "server": server,
                    "detailed": "true" if detailed else "false"
                },
                timeout=200  # 3+ минуты для detailed
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {
                "status": "error",
                "error": "connection_failed",
                "message": str(e)
            }

# views.py
from .services.installation_client import InstallationServiceClient

def sync_databases(request):
    client = InstallationServiceClient()
    result = client.get_infobases(detailed=True)

    if result['status'] == 'success':
        # Синхронизировать базы с Django моделями
        for infobase in result['infobases']:
            Database.objects.update_or_create(
                uuid=infobase['uuid'],
                defaults={
                    'name': infobase['name'],
                    'description': infobase['description'],
                    'dbms': infobase.get('dbms', ''),
                    'db_server': infobase.get('db_server', ''),
                    'connection_string': infobase.get('connection_string', ''),
                }
            )
        return JsonResponse({'message': 'Sync completed'})
    else:
        return JsonResponse(result, status=500)
```

## Тестирование

### Проверка RAC

```bash
# Вручную проверить RAC
"C:\Program Files\1cv8\8.3.27.1786\bin\rac.exe" localhost:1545 cluster list
```

### Локальное тестирование API

```bash
# С использованием PowerShell
Invoke-RestMethod -Uri "http://localhost:8085/api/v1/infobases?server=localhost:1545"

# С использованием curl
curl.exe "http://localhost:8085/api/v1/infobases?server=localhost:1545"
```

## Troubleshooting

### Ошибка: "RAC executable not found"

**Решение:** Проверьте путь к rac.exe

```bash
# Установить правильный путь через environment variable
set RAC_PATH=C:\1C\bin\rac.exe
go run cmd/main.go
```

### Ошибка: "Failed to connect to RAS"

**Решение:** Проверьте, что RAS сервер запущен

```bash
# Проверить подключение к RAS
"C:\Program Files\1cv8\8.3.27.1786\bin\rac.exe" localhost:1545 cluster list
```

### Медленные запросы

**Решение:** Используйте `detailed=false` для быстрых запросов

```bash
# Быстрый запрос (1-2 секунды)
curl "http://localhost:8085/api/v1/infobases?server=localhost:1545&detailed=false"

# Медленный запрос (10-30 секунд для 10 баз)
curl "http://localhost:8085/api/v1/infobases?server=localhost:1545&detailed=true"
```

## Production Deployment

### Systemd Service (если используется WSL)

```ini
[Unit]
Description=Installation Service
After=network.target

[Service]
Type=simple
User=service-user
WorkingDirectory=/opt/installation-service
Environment="RAC_PATH=C:\Program Files\1cv8\8.3.27.1786\bin\rac.exe"
Environment="API_SERVER_PORT=8085"
Environment="LOG_LEVEL=info"
ExecStart=/opt/installation-service/installation-service.exe
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Windows Service

Используйте утилиту `nssm` (Non-Sucking Service Manager):

```cmd
nssm install InstallationService "C:\Services\installation-service\installation-service.exe"
nssm set InstallationService AppDirectory "C:\Services\installation-service"
nssm set InstallationService AppEnvironmentExtra "RAC_PATH=C:\1C\rac.exe"
nssm start InstallationService
```

## Мониторинг

### Health Check

```bash
# Простая проверка
curl http://localhost:8085/health

# С интервалом
watch -n 5 'curl -s http://localhost:8085/health | jq'
```

### Prometheus Metrics (будет добавлено)

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'installation-service'
    static_configs:
      - targets: ['windows-server:8085']
```

## Дальнейшее развитие

- [ ] Добавить кэширование результатов
- [ ] Реализовать метрики Prometheus
- [ ] Добавить поддержку аутентификации
- [ ] Реализовать batch запросы
- [ ] Добавить unit и integration тесты
- [ ] Реализовать graceful reload конфигурации
