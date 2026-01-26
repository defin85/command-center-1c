# Databases Services Layer

## Обзор

Сервисный слой для работы с базами данных 1C:Enterprise, OData операциями и управлением кластерами.

## Файлы

```
orchestrator/apps/databases/
├── services.py                          # Основной сервисный слой
├── models.py                            # Модели данных (Cluster, Database, DatabaseGroup)
├── clients/
│   └── installation_service.py          # HTTP клиент для installation-service
├── odata/                               # OData клиент и session management
├── admin.py                             # Django Admin interface
└── CLUSTER_SERVICE_IMPLEMENTATION.md    # Детальная документация ClusterService
```

## Сервисы

### 1. DatabaseService

**Назначение:** Управление базами данных и health checks.

**Методы:**
- `health_check_database(database)` - проверка одной базы
- `health_check_group(group)` - проверка группы баз
- `bulk_create_databases(databases_data)` - массовое создание баз

**Пример:**
```python
from apps.databases.models import Database
from apps.databases.services import DatabaseService

db = Database.objects.get(name="accounting")
result = DatabaseService.health_check_database(db)
# {'healthy': True, 'response_time': 145.3, 'status_code': 200}
```

---

### 2. ODataOperationService

**Назначение:** Выполнение OData операций с базами 1C.

**Методы:**
- `create_entity(database, entity_type, entity_name, data)` - создание сущности
- `get_entities(database, entity_type, entity_name, filter_query)` - получение списка

**Пример:**
```python
from apps.databases.services import ODataOperationService

result = ODataOperationService.create_entity(
    database=db,
    entity_type="Catalog",
    entity_name="Пользователи",
    data={"Наименование": "Иванов И.И."}
)
# {'success': True, 'data': {...}}
```

---

### 3. ClusterService ⭐

**Назначение:** Управление кластерами 1C и синхронизация инфобаз.

**Методы:**

#### Публичные
- `create_from_ras(ras_server, installation_service_url, cluster_user, cluster_pwd)`
  - Создание кластера через RAS

- `sync_infobases(cluster)`
  - Синхронизация инфобаз из кластера

#### Приватные
- `_import_infobases(cluster, infobases)` - импорт в Database модель
- `_parse_host(db_server)` - парсинг хоста
- `_build_odata_url(ib, default_host)` - построение OData URL

**Пример:**
```python
from apps.databases.services import ClusterService

# 1. Создать кластер
cluster = ClusterService.create_from_ras(
    ras_server="localhost:1545",
    installation_service_url="http://localhost:8085"
)

# 2. Синхронизировать инфобазы
result = ClusterService.sync_infobases(cluster)
# {'created': 5, 'updated': 10, 'errors': 0}

# 3. Проверить импортированные базы
print(f"Databases in cluster: {cluster.databases.count()}")
```

---

## Архитектура взаимодействия

```
┌─────────────────┐
│  Django Admin   │
└────────┬────────┘
         │
┌────────▼────────────────────────────┐
│      Services Layer                 │
│  ┌─────────────────────────────┐   │
│  │  DatabaseService            │   │
│  │  - health_check_database()  │   │
│  │  - health_check_group()     │   │
│  │  - bulk_create_databases()  │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  ODataOperationService      │   │
│  │  - create_entity()          │   │
│  │  - get_entities()           │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  ClusterService             │   │
│  │  - create_from_ras()        │   │
│  │  - sync_infobases()         │   │
│  └─────────────────────────────┘   │
└────────┬────────────────┬───────────┘
         │                │
    ┌────▼────┐      ┌────▼──────────────────┐
    │  OData  │      │ InstallationService   │
    │ Client  │      │     HTTP Client       │
    └────┬────┘      └────┬──────────────────┘
         │                │
    ┌────▼──────┐    ┌────▼────┐
    │ 1C Bases  │    │  RAS    │
    │  (OData)  │    │ Server  │
    └───────────┘    └─────────┘
```

## Основные сценарии использования

### Сценарий 1: Настройка нового кластера

```python
from apps.databases.services import ClusterService

# 1. Подключиться к RAS и создать кластер
cluster = ClusterService.create_from_ras(
    ras_server="192.168.1.100:1545",
    installation_service_url="http://installation-service:8085",
    cluster_user="admin",
    cluster_pwd="password"
)

# 2. Синхронизировать все инфобазы
result = ClusterService.sync_infobases(cluster)

# 3. Настроить credentials для каждой базы (вручную через Admin)
for db in cluster.databases.all():
    db.username = "odata_user"
    db.password = "secure_password"
    db.status = Database.STATUS_ACTIVE
    db.save()
```

### Сценарий 1.1: Маппинги пользователей для `ibcmd` (IB + DBMS)

Для schema-driven `ibcmd_cli` креды не вводятся в UI напрямую:
- IB creds берутся из `InfobaseUserMapping` (см. API v2 `databases/*-ib-user*`).
- DBMS creds для offline-подключения берутся из `DbmsUserMapping` (см. API v2 `databases/*-dbms-user*`).

Оба типа маппинга поддерживают service-аккаунты (поле `is_service=true`). Политика разрешений на их использование задаётся на уровне операций (RBAC/allowlist).

### Сценарий 2: Health Check всех баз

```python
from apps.databases.models import DatabaseGroup
from apps.databases.services import DatabaseService

# Создать группу "Production"
group = DatabaseGroup.objects.get(name="Production")

# Проверить здоровье всех баз в группе
result = DatabaseService.health_check_group(group)
print(f"Healthy: {result['healthy']}/{result['total']}")
```

### Сценарий 3: Массовые OData операции

```python
from apps.databases.models import Database
from apps.databases.services import ODataOperationService

# Получить все активные базы
databases = Database.objects.filter(
    status=Database.STATUS_ACTIVE,
    cluster__name="Production"
)

# Создать пользователя в каждой базе
for db in databases:
    result = ODataOperationService.create_entity(
        database=db,
        entity_type="Catalog",
        entity_name="Пользователи",
        data={"Наименование": "Новый Пользователь"}
    )
    if result['success']:
        print(f"[{db.name}] ✓ Created")
    else:
        print(f"[{db.name}] ✗ Error: {result['error']}")
```

### Сценарий 4: Периодическая синхронизация (Celery)

```python
from celery import shared_task
from apps.databases.models import Cluster
from apps.databases.services import ClusterService

@shared_task
def sync_all_clusters():
    """Celery task для синхронизации всех кластеров."""
    for cluster in Cluster.objects.filter(status=Cluster.STATUS_ACTIVE):
        try:
            result = ClusterService.sync_infobases(cluster)
            print(f"[{cluster.name}] Synced: {result}")
        except Exception as e:
            print(f"[{cluster.name}] Error: {e}")
```

## Обработка ошибок

### Типы исключений

1. **ValueError** - валидационные ошибки
   ```python
   try:
       cluster = ClusterService.create_from_ras(...)
   except ValueError as e:
       # Кластер уже существует или недоступен
       print(f"Validation error: {e}")
   ```

2. **ODataError** - ошибки OData API
   ```python
   from apps.databases.odata import ODataError

   try:
       result = ODataOperationService.create_entity(...)
   except ODataError as e:
       # OData API вернул ошибку
       print(f"OData error: {e}")
   ```

3. **Exception** - неожиданные ошибки
   ```python
   try:
       result = ClusterService.sync_infobases(cluster)
   except Exception as e:
       # Unexpected error
       print(f"Error: {e}")
   ```

### Логирование

Все сервисы используют Python logging:

```python
import logging
logger = logging.getLogger(__name__)

# INFO - успешные операции
# WARNING - пропущенные элементы
# ERROR - ошибки с traceback
```

## Конфигурация

### Settings.py

```python
# Installation Service URL
INSTALLATION_SERVICE_URL = 'http://localhost:8085'

# OData settings
ODATA_TIMEOUT = 30  # seconds
ODATA_MAX_RETRIES = 3
```

## Тестирование

```bash
# Проверка логики ClusterService
cd orchestrator
python test_cluster_service.py

# Django unit tests (будут добавлены в Phase 2)
python manage.py test apps.databases
```

## Следующие шаги (Roadmap)

**Phase 1 (Текущая):**
- ✅ Базовые модели (Cluster, Database)
- ✅ ClusterService с синхронизацией
- ✅ DatabaseService с health checks
- ✅ ODataOperationService

**Phase 2 (Next):**
- ⏳ REST API endpoints для Cluster CRUD
- ⏳ Celery tasks для периодической синхронизации
- ⏳ Unit tests для всех сервисов
- ⏳ Integration tests с mock installation-service

**Phase 3 (Future):**
- ⏳ WebSocket notifications для real-time sync status
- ⏳ Advanced filtering и pagination
- ⏳ Batch operations API

## Документация

- **Детальная документация ClusterService**: `CLUSTER_SERVICE_IMPLEMENTATION.md`
- **API Endpoints** (будет добавлена): `docs/api/clusters.md`
- **Architecture**: `docs/architecture/services-layer.md` (TODO)

## Контакты и поддержка

Для вопросов и предложений:
- GitHub Issues: `command-center-1c/issues`
- Team: Backend Team

---

**Версия:** 1.0
**Дата:** 2025-01-17
**Статус:** Phase 1 Complete ✅
