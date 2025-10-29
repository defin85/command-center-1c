# ClusterService Implementation

## Обзор

Класс `ClusterService` реализован в файле `orchestrator/apps/databases/services.py` и предоставляет функциональность для работы с кластерами 1C:Enterprise и синхронизации информационных баз.

## Архитектура

```
ClusterService
    ├── create_from_ras()       # Создание кластера через подключение к RAS
    ├── sync_infobases()        # Синхронизация инфобаз из кластера
    ├── _import_infobases()     # Импорт инфобаз в модель Database
    ├── _parse_host()           # Парсинг хоста из строки db_server
    └── _build_odata_url()      # Построение OData URL для инфобазы
```

## Публичные методы

### 1. create_from_ras()

**Назначение:** Создание кластера через подключение к RAS серверу.

**Сигнатура:**
```python
@staticmethod
def create_from_ras(
    ras_server: str,
    installation_service_url: str,
    cluster_user: str = None,
    cluster_pwd: str = None
) -> Cluster
```

**Алгоритм:**
1. Подключение к installation-service
2. Health check сервиса
3. Вызов `get_infobases(detailed=False)` для получения cluster_id и cluster_name
4. Проверка существования кластера (по id и по ras_server+name)
5. Создание объекта Cluster

**Исключения:**
- `ValueError`: Если кластер уже существует или подключение не удалось
- `Exception`: При других ошибках

**Пример использования:**
```python
from apps.databases.services import ClusterService

cluster = ClusterService.create_from_ras(
    ras_server="localhost:1545",
    installation_service_url="http://localhost:8085",
    cluster_user="admin",
    cluster_pwd="password"
)
```

### 2. sync_infobases()

**Назначение:** Синхронизация информационных баз из кластера.

**Сигнатура:**
```python
@staticmethod
@transaction.atomic
def sync_infobases(cluster: Cluster) -> Dict[str, int]
```

**Алгоритм:**
1. Подключение к installation-service
2. Health check сервиса
3. Вызов `get_infobases(detailed=True)` для получения полной информации
4. Импорт инфобаз через `_import_infobases()`
5. Обновление статуса синхронизации кластера

**Возвращает:**
```python
{
    'created': 5,   # Количество созданных баз
    'updated': 10,  # Количество обновленных баз
    'errors': 0     # Количество ошибок
}
```

**Пример использования:**
```python
cluster = Cluster.objects.get(name="Main Cluster")
result = ClusterService.sync_infobases(cluster)
print(f"Created: {result['created']}, Updated: {result['updated']}")
```

## Приватные методы

### 3. _import_infobases()

**Назначение:** Импорт списка инфобаз в модель Database.

**Сигнатура:**
```python
@staticmethod
def _import_infobases(cluster: Cluster, infobases: list) -> Tuple[int, int, int]
```

**Алгоритм:**
Для каждой инфобазы:
1. Извлечение uuid и name
2. Парсинг хоста через `_parse_host()`
3. Построение OData URL через `_build_odata_url()`
4. Формирование metadata с полной информацией
5. Создание/обновление записи Database через `update_or_create()`

**Возвращает:** `(created_count, updated_count, error_count)`

**Metadata структура:**
```python
{
    'dbms': 'PostgreSQL',
    'db_server': 'localhost',
    'db_name': 'test_db',
    'db_user': 'postgres',
    'security_level': 0,
    'connection_string': '...',
    'locale': 'ru_RU',
    'imported_from_cluster': True,
    'import_timestamp': '2025-01-17T10:00:00',
    'ras_server': 'localhost:1545',
    'cluster_id': 'cluster-uuid',
    'cluster_name': 'Main Cluster',
}
```

### 4. _parse_host()

**Назначение:** Извлечение хоста из строки db_server.

**Сигнатура:**
```python
@staticmethod
def _parse_host(db_server: str) -> str
```

**Примеры:**
- `'sql-server\\SQLEXPRESS'` → `'sql-server'`
- `'localhost'` → `'localhost'`
- `''` → `''`

### 5. _build_odata_url()

**Назначение:** Построение OData URL для инфобазы.

**Сигнатура:**
```python
@staticmethod
def _build_odata_url(ib: dict, default_host: str) -> str
```

**Формат:** `http://host/base_name/odata/standard.odata/`

**Примеры:**
- `{'name': 'accounting'}`, `'server1'` → `'http://server1/accounting/odata/standard.odata/'`
- `{'name': 'test_base'}`, `'localhost'` → `'http://localhost/test_base/odata/standard.odata/'`

## Обработка ошибок

### Логирование

Все методы используют структурированное логирование:
- **INFO**: Успешные операции, основные этапы
- **WARNING**: Пропущенные инфобазы (отсутствует uuid/name)
- **ERROR**: Ошибки подключения, импорта, валидации

### Транзакции

Метод `sync_infobases()` использует `@transaction.atomic` для атомарности операций.

### Исключения

- `ValueError`: Валидационные ошибки, недоступность сервисов
- `Exception`: Неожиданные ошибки (с полным traceback)

## Интеграция с installation-service

ClusterService использует `InstallationServiceClient` для взаимодействия с Go микросервисом:

```python
with InstallationServiceClient(base_url=cluster.installation_service_url) as client:
    if not client.health_check():
        raise ValueError("Service not available")

    result = client.get_infobases(
        server=cluster.ras_server,
        cluster_user=cluster.cluster_user or None,
        cluster_pwd=cluster.cluster_pwd or None,
        detailed=True
    )
```

## Управление статусами

### Статусы кластера

- **ACTIVE**: Кластер активен и доступен
- **INACTIVE**: Кластер неактивен
- **ERROR**: Ошибка синхронизации
- **MAINTENANCE**: Режим обслуживания

### Статусы синхронизации

- **pending**: Ожидает первой синхронизации
- **success**: Последняя синхронизация успешна
- **failed**: Последняя синхронизация неудачна

Метод `cluster.mark_sync(success, error_message)` автоматически управляет статусами.

## Работа с Database записями

### Начальный статус

Все импортированные базы создаются со статусом `STATUS_INACTIVE` до настройки credentials:

```python
'status': Database.STATUS_INACTIVE,  # Inactive until credentials configured
'username': '',  # Will be set manually by admin
'password': '',  # Will be set manually by admin
```

### Поля Database

- **id**: UUID инфобазы из 1C
- **name**: Имя инфобазы
- **host**: Хост (парсится из db_server)
- **port**: 80 (по умолчанию)
- **base_name**: Имя инфобазы (дубль name)
- **odata_url**: Полный OData URL
- **cluster**: ForeignKey на Cluster
- **metadata**: JSON с полной информацией

## Тестирование

Реализован тестовый скрипт `test_cluster_service.py` для проверки логики:

```bash
cd orchestrator
python test_cluster_service.py
```

**Тесты:**
- ✓ _parse_host() - парсинг хостов
- ✓ _build_odata_url() - построение URL
- ✓ Metadata структура - проверка всех полей
- ✓ Error handling - обработка невалидных данных

## Примеры использования

### Сценарий 1: Создание и синхронизация кластера

```python
from apps.databases.services import ClusterService
from apps.databases.models import Cluster

# 1. Создать кластер
cluster = ClusterService.create_from_ras(
    ras_server="localhost:1545",
    installation_service_url="http://localhost:8085"
)

print(f"Created cluster: {cluster.name} (id={cluster.id})")
print(f"Status: {cluster.status}, Sync: {cluster.last_sync_status}")

# 2. Синхронизировать инфобазы
result = ClusterService.sync_infobases(cluster)
print(f"Sync result: {result}")

# 3. Проверить созданные базы
databases = cluster.databases.all()
print(f"Total databases: {databases.count()}")

for db in databases:
    print(f"- {db.name}: {db.odata_url}")
```

### Сценарий 2: Периодическая синхронизация

```python
from apps.databases.models import Cluster
from apps.databases.services import ClusterService

# Синхронизировать все активные кластеры
for cluster in Cluster.objects.filter(status=Cluster.STATUS_ACTIVE):
    try:
        result = ClusterService.sync_infobases(cluster)
        print(f"[{cluster.name}] OK: {result}")
    except Exception as e:
        print(f"[{cluster.name}] ERROR: {e}")
```

### Сценарий 3: Обработка ошибок

```python
from apps.databases.services import ClusterService

try:
    cluster = ClusterService.create_from_ras(
        ras_server="invalid:9999",
        installation_service_url="http://localhost:8085"
    )
except ValueError as e:
    print(f"Validation error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Ограничения и рекомендации

### Ограничения

1. **OData credentials**: Не импортируются автоматически, требуют ручной настройки
2. **HTTP only**: OData URL строится только для HTTP (не HTTPS)
3. **Default port**: Всегда используется порт 80 для OData
4. **No deletion**: Удаление инфобаз из кластера не удаляет Database записи

### Рекомендации

1. **Регулярная синхронизация**: Запускайте sync_infobases() периодически (например, через Celery task)
2. **Health checks**: Проверяйте доступность installation-service перед операциями
3. **Error monitoring**: Следите за `last_sync_status` и `last_sync_error` кластеров
4. **Credentials**: Настраивайте username/password для Database после импорта
5. **Status management**: Активируйте базы (`STATUS_ACTIVE`) после настройки credentials

## Связанные файлы

- **Модели**: `orchestrator/apps/databases/models.py`
- **Клиент**: `orchestrator/apps/databases/clients/installation_service.py`
- **Тесты**: `orchestrator/test_cluster_service.py`
- **Админка**: `orchestrator/apps/databases/admin.py`

## История изменений

- **2025-01-17**: Первая реализация ClusterService с полной функциональностью
