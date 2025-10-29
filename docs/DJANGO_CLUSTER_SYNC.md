# Django Admin: Sync Databases from 1C Cluster

Документация по функциональности синхронизации баз данных 1С из кластера через Django Admin.

## Обзор

Эта функция позволяет импортировать список баз данных 1С из кластера в Django Database модель через удобный web-интерфейс Django Admin.

### Архитектура

```
Django Admin → InstallationServiceClient → installation-service (Go) → 1C RAS → Cluster
     ↓
  Database Model (PostgreSQL)
```

## Использование

### 1. Запуск installation-service

Перед использованием убедитесь, что installation-service запущен:

```bash
# В директории go-services/installation-service
go run cmd/main.go

# Или через Docker
docker run -p 8085:8085 installation-service
```

Проверьте доступность:

```bash
curl http://localhost:8085/health
# Ожидаемый ответ: 200 OK
```

### 2. Открыть Django Admin

1. Перейдите в Django Admin: http://localhost:8000/admin/
2. Войдите как superuser
3. Откройте раздел **1C Databases**

### 3. Запустить синхронизацию

**Вариант А: Через Action**

1. Выберите любые базы (или не выбирайте)
2. В выпадающем меню Actions выберите **"Sync databases from 1C cluster"**
3. Нажмите **Go**

**Вариант Б: Прямой URL**

Перейдите по ссылке:
```
http://localhost:8000/admin/databases/database/sync-from-cluster/
```

### 4. Workflow синхронизации

#### Шаг 1: Параметры подключения к кластеру

Заполните форму:

- **RAS Server Address**: `localhost:1545` (по умолчанию)
- **Cluster Administrator Username**: оставьте пустым, если аутентификация не требуется
- **Cluster Administrator Password**: оставьте пустым, если аутентификация не требуется
- **Get detailed information**: ✓ (рекомендуется для получения полных метаданных)

Нажмите **Get Database List**.

**Время выполнения:**
- Без детальной информации: ~1-2 секунды
- С детальной информацией: ~10-30 секунд для 2-10 баз

#### Шаг 2: Выбор баз для импорта

Отобразится таблица со всеми найденными базами:

| Select | Name | Description | DBMS | Database Server | Database Name |
|--------|------|-------------|------|-----------------|---------------|
| ✓ | accounting_prod | Production | PostgreSQL | localhost | accounting_db |
| ✓ | hr_system | HR System | MSSQLServer | sql-server\\SQLEXPRESS | hr_db |

Используйте кнопки:
- **Select All** - выбрать все базы
- **Deselect All** - снять все галочки

Нажмите **Import Selected Databases**.

#### Шаг 3: Импорт завершен

Вы будете перенаправлены в changelist с сообщениями:

- ✅ **Success**: "Successfully created 2 database(s)."
- ℹ️ **Info**: "Updated 1 existing database(s)."
- ❌ **Error**: "Failed to import 1 database(s). Check logs for details."

## Что происходит при импорте

### Создание / обновление базы данных

Для каждой выбранной базы выполняется `Database.objects.update_or_create()`:

- **Primary Key**: UUID базы из кластера (уникальный идентификатор)
- **Status**: `INACTIVE` (по умолчанию)
- **OData credentials**: Пустые (требуют ручной настройки)

### Поля Database модели

```python
Database.objects.create(
    id=ib['uuid'],                    # UUID из кластера
    name=ib['name'],                  # Имя базы
    description=ib.get('description'),
    host='localhost',                 # Извлекается из db_server
    port=80,                          # Default OData port
    base_name=ib['name'],
    odata_url='http://localhost/base_name/odata/standard.odata/',
    username='',                      # ❗ Требует ручной настройки
    password='',                      # ❗ Требует ручной настройки
    status='inactive',                # ❗ Изменить на 'active' вручную
    metadata={
        'dbms': 'PostgreSQL',
        'db_server': 'localhost\\SQLEXPRESS',
        'db_name': 'accounting_db',
        'db_user': 'dbuser',
        'security_level': 0,
        'connection_string': '...',
        'locale': 'ru_RU',
        'imported_from_cluster': True,
        'import_timestamp': '2025-01-17T10:30:45.123Z',
        'ras_server': 'localhost:1545'
    }
)
```

## После импорта

### ❗ Обязательные действия

1. **Установить OData credentials** для каждой базы:
   - Откройте базу в Django Admin
   - Установите `username` и `password` (для OData доступа)
   - Сохраните

2. **Активировать базу**:
   - Измените `status` с `inactive` на `active`
   - Сохраните

3. **Проверить подключение**:
   - Выберите базу в changelist
   - Запустите Action: **"Health check selected databases"**
   - Проверьте результат

### Пример настройки после импорта

```python
# В Django shell
from apps.databases.models import Database

db = Database.objects.get(name='accounting_prod')

# Установить credentials
db.username = 'odata_user'
db.password = 'secure_password'
db.status = Database.STATUS_ACTIVE
db.save()

# Проверить подключение
from apps.databases.services import DatabaseService
result = DatabaseService.health_check_database(db)
print(result)  # {'healthy': True, 'response_time': 0.123}
```

## Обновление существующих баз

Если база с таким UUID уже существует:

- **Обновляются**: метаданные кластера (dbms, db_server, etc.)
- **НЕ обновляются**: OData credentials (username, password), status

Это позволяет безопасно повторять синхронизацию для обновления метаданных.

## Troubleshooting

### Installation-service недоступен

**Ошибка:**
```
Installation-service is not available. Please ensure the service is running.
```

**Решение:**
1. Проверить, что installation-service запущен: `curl http://localhost:8085/health`
2. Проверить `INSTALLATION_SERVICE_URL` в `.env`
3. Проверить логи installation-service

### Timeout при получении списка баз

**Ошибка:**
```
Failed to retrieve database list: Timeout
```

**Решение:**
1. Увеличить `INSTALLATION_SERVICE_TIMEOUT` в `.env` (по умолчанию: 180 секунд)
2. Попробовать без детальной информации (быстрее)
3. Проверить доступность 1C RAS сервера

### Неверный формат ответа

**Ошибка:**
```
Failed to retrieve database list: Response missing 'status' field
```

**Решение:**
1. Проверить версию installation-service (должна поддерживать API v1)
2. Проверить логи installation-service на наличие ошибок
3. Попробовать вызвать API напрямую: `curl "http://localhost:8085/api/v1/infobases?server=localhost:1545"`

### Не удается импортировать конкретную базу

**Ошибка в логах:**
```
ERROR: Failed to import infobase 'accounting_prod': ...
```

**Решение:**
1. Проверить логи Django Orchestrator для детальной информации
2. Убедиться, что UUID базы валиден
3. Проверить ограничения Database модели (unique constraints, etc.)

## Конфигурация

### Environment Variables

```bash
# .env
INSTALLATION_SERVICE_URL=http://localhost:8085
INSTALLATION_SERVICE_TIMEOUT=180
```

### Django Settings

```python
# orchestrator/config/settings/base.py
INSTALLATION_SERVICE_URL = env('INSTALLATION_SERVICE_URL', default='http://localhost:8085')
INSTALLATION_SERVICE_TIMEOUT = int(env('INSTALLATION_SERVICE_TIMEOUT', default='180'))
```

## Безопасность

### Разрешения

- ✅ Только **superusers** могут запускать синхронизацию
- ✅ CSRF protection включен
- ✅ Session-based authentication

### Логирование

Пароли кластера НЕ логируются:

```python
# В логах
INFO: Calling installation-service: GET /api/v1/infobases with params={'cluster_pwd': '***'}
```

### Шифрование

Database.password шифруется через `django-encrypted-model-fields`:

```python
from encrypted_model_fields.fields import EncryptedCharField

class Database(models.Model):
    password = EncryptedCharField(max_length=255)
```

Требуется `DB_ENCRYPTION_KEY` в `.env`.

## API Reference

### InstallationServiceClient

См. `orchestrator/apps/databases/clients/README.md`

### Django Admin URLs

```
GET  /admin/databases/database/sync-from-cluster/
     → Форма параметров кластера

POST /admin/databases/database/sync-from-cluster/
     step=1 → Получить список баз
     step=2 → Импортировать выбранные базы
```

### Templates

- `admin/databases/sync_from_cluster_form.html` - форма параметров
- `admin/databases/sync_from_cluster_select.html` - выбор баз для импорта

## Примеры использования

### Программный импорт (без UI)

```python
from apps.databases.clients import InstallationServiceClient
from apps.databases.models import Database
from django.utils import timezone

# Получить список баз
client = InstallationServiceClient()
result = client.get_infobases(
    server='localhost:1545',
    cluster_user='admin',
    cluster_pwd='password',
    detailed=True
)

# Импортировать все базы
for ib in result['infobases']:
    Database.objects.update_or_create(
        id=ib['uuid'],
        defaults={
            'name': ib['name'],
            'description': ib.get('description', ''),
            'host': 'localhost',
            'port': 80,
            'base_name': ib['name'],
            'odata_url': f"http://localhost/{ib['name']}/odata/standard.odata/",
            'username': '',
            'password': '',
            'status': Database.STATUS_INACTIVE,
            'metadata': {
                'imported_from_cluster': True,
                'import_timestamp': timezone.now().isoformat(),
                **ib
            }
        }
    )
```

### Management Command (будущая реализация)

```bash
# Предложение для будущей реализации
python manage.py sync_databases_from_cluster \
    --server=localhost:1545 \
    --cluster-user=admin \
    --detailed
```

## Ограничения

1. **Не импортируются автоматически**:
   - OData credentials (username/password)
   - Status (всегда INACTIVE)
   - Health check данные

2. **Требуется ручная настройка после импорта**:
   - Установить OData credentials
   - Активировать базу
   - Проверить подключение

3. **Timeout**:
   - По умолчанию 180 секунд
   - Может быть недостаточно для очень больших кластеров (100+ баз)

4. **Permissions**:
   - Только superusers
   - Нельзя делегировать обычным пользователям

## Roadmap

**Phase 1 (Current)**:
- ✅ HTTP client для installation-service
- ✅ Django Admin action для синхронизации
- ✅ Intermediate pages для workflow
- ✅ Импорт в Database модель

**Phase 2 (Future)**:
- ⏳ Management command для CLI
- ⏳ Автоматическая проверка credentials после импорта
- ⏳ Bulk activation базы
- ⏳ Scheduled sync (Celery task)

**Phase 3 (Future)**:
- ⏳ REST API endpoint для синхронизации
- ⏳ Frontend integration (React)
- ⏳ Real-time sync status via WebSocket

## См. также

- [Installation Service API Documentation](../go-services/installation-service/README.md)
- [Database Model Documentation](../orchestrator/apps/databases/README.md)
- [Django Admin Customization](https://docs.djangoproject.com/en/4.2/ref/contrib/admin/)
