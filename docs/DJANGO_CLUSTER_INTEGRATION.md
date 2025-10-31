# Django Orchestrator + cluster-service Integration

**Статус:** Актуально для CommandCenter1C
**Версия:** 1.0
**Дата:** 2025-10-31

Практический гайд по интеграции Django Orchestrator с cluster-service через gRPC.

---

## 🎯 Архитектура

```
Django Admin/API → Django Services Layer → gRPC Client → cluster-service (Go)
                                                              ↓
                                                          ras-grpc-gw
                                                              ↓
                                                           RAS → 1C Кластеры
```

**Цель:** Django управляет метаданными кластеров и баз в PostgreSQL, а cluster-service предоставляет real-time данные от 1С.

---

## 📦 Модели Django

### Cluster Model

**Файл:** `orchestrator/apps/databases/models.py`

```python
class Cluster(models.Model):
    cluster_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    host = models.CharField(max_length=255)
    port = models.IntegerField(default=1541)
    admin_user = models.CharField(max_length=255, blank=True)
    admin_password = models.CharField(max_length=255, blank=True)

    # Мета-информация
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"
```

### Infobase Model

```python
class Infobase(models.Model):
    infobase_id = models.CharField(max_length=255, unique=True)
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='infobases')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Состояние
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} @ {self.cluster.name}"
```

**Зачем нужны модели:**
- Хранение постоянной конфигурации кластеров
- Связь с другими Django моделями (операции, задачи)
- Административный интерфейс
- Аудит и история изменений

---

## 🔌 gRPC Client (Django)

### Установка зависимостей

```bash
pip install grpcio grpcio-tools
```

### Генерация Python клиента

```bash
# Из protobuf определений cluster-service
python -m grpc_tools.protoc \
  -I ./go-services/cluster-service/proto \
  --python_out=./orchestrator/apps/databases/grpc \
  --grpc_python_out=./orchestrator/apps/databases/grpc \
  cluster_service.proto
```

### ClusterServiceClient

**Файл:** `orchestrator/apps/databases/services/cluster_service_client.py`

```python
import grpc
from ..grpc import cluster_service_pb2, cluster_service_pb2_grpc

class ClusterServiceClient:
    def __init__(self, host='localhost', port=50051):
        self.channel = grpc.insecure_channel(f'{host}:{port}')
        self.stub = cluster_service_pb2_grpc.ClusterServiceStub(self.channel)

    def get_clusters(self):
        """Получить список всех кластеров"""
        request = cluster_service_pb2.GetClustersRequest()
        response = self.stub.GetClusters(request)
        return response.clusters

    def get_infobases(self, cluster_id):
        """Получить список баз данных кластера"""
        request = cluster_service_pb2.GetInfobasesRequest(
            cluster_id=cluster_id
        )
        response = self.stub.GetInfobases(request)
        return response.infobases

    def close(self):
        self.channel.close()
```

---

## 🔄 Синхронизация данных

### ClusterSyncService

**Файл:** `orchestrator/apps/databases/services/cluster_sync.py`

```python
from django.utils import timezone
from ..models import Cluster, Infobase
from .cluster_service_client import ClusterServiceClient

class ClusterSyncService:
    def __init__(self):
        self.client = ClusterServiceClient()

    def sync_all_clusters(self):
        """Синхронизировать все кластеры из cluster-service"""
        try:
            clusters = self.client.get_clusters()

            for cluster_data in clusters:
                cluster, created = Cluster.objects.update_or_create(
                    cluster_id=cluster_data.cluster_id,
                    defaults={
                        'name': cluster_data.name,
                        'host': cluster_data.host,
                        'port': cluster_data.port,
                        'is_active': True,
                        'last_sync': timezone.now(),
                    }
                )

                if created:
                    print(f"Created cluster: {cluster.name}")
                else:
                    print(f"Updated cluster: {cluster.name}")

                # Синхронизировать базы данных кластера
                self.sync_cluster_infobases(cluster)

        finally:
            self.client.close()

    def sync_cluster_infobases(self, cluster):
        """Синхронизировать базы данных кластера"""
        try:
            infobases = self.client.get_infobases(cluster.cluster_id)

            for infobase_data in infobases:
                Infobase.objects.update_or_create(
                    infobase_id=infobase_data.infobase_id,
                    defaults={
                        'cluster': cluster,
                        'name': infobase_data.name,
                        'description': infobase_data.description or '',
                        'is_active': True,
                        'last_sync': timezone.now(),
                    }
                )

        except Exception as e:
            print(f"Error syncing infobases for {cluster.name}: {e}")
```

### Использование в Django Management Command

```python
# orchestrator/apps/databases/management/commands/sync_clusters.py
from django.core.management.base import BaseCommand
from apps.databases.services.cluster_sync import ClusterSyncService

class Command(BaseCommand):
    help = 'Sync clusters and infobases from cluster-service'

    def handle(self, *args, **options):
        self.stdout.write('Starting cluster sync...')

        service = ClusterSyncService()
        service.sync_all_clusters()

        self.stdout.write(self.style.SUCCESS('Cluster sync complete!'))
```

**Запуск:**
```bash
python manage.py sync_clusters
```

---

## 🎛️ Django Admin Integration

### ClusterAdmin

**Файл:** `orchestrator/apps/databases/admin.py`

```python
from django.contrib import admin
from .models import Cluster, Infobase
from .services.cluster_sync import ClusterSyncService

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ['name', 'host', 'port', 'is_active', 'last_sync']
    list_filter = ['is_active', 'last_sync']
    search_fields = ['name', 'host', 'cluster_id']
    readonly_fields = ['cluster_id', 'last_sync']

    actions = ['sync_cluster']

    @admin.action(description='Sync selected clusters')
    def sync_cluster(self, request, queryset):
        service = ClusterSyncService()
        for cluster in queryset:
            service.sync_cluster_infobases(cluster)
        self.message_user(request, f'{queryset.count()} clusters synced')

@admin.register(Infobase)
class InfobaseAdmin(admin.ModelAdmin):
    list_display = ['name', 'cluster', 'is_active', 'last_sync']
    list_filter = ['is_active', 'cluster', 'last_sync']
    search_fields = ['name', 'infobase_id', 'description']
    readonly_fields = ['infobase_id', 'last_sync']
```

**Возможности:**
- ✅ Просмотр всех кластеров и баз
- ✅ Фильтрация по статусу, дате синхронизации
- ✅ Ручная синхронизация через Admin Actions
- ✅ Поиск по имени, ID, хосту

---

## ⚙️ Конфигурация

### Django Settings

```python
# orchestrator/config/settings.py

CLUSTER_SERVICE = {
    'HOST': env('CLUSTER_SERVICE_HOST', default='localhost'),
    'PORT': env.int('CLUSTER_SERVICE_PORT', default=50051),
    'TIMEOUT': 30,  # seconds
}
```

### Environment Variables

```bash
# .env
CLUSTER_SERVICE_HOST=localhost
CLUSTER_SERVICE_PORT=50051
```

---

## 🚀 Quick Start

### 1. Запустить cluster-service

```bash
cd go-services/cluster-service
go run cmd/main.go
```

### 2. Применить миграции Django

```bash
cd orchestrator
python manage.py makemigrations databases
python manage.py migrate
```

### 3. Синхронизировать кластеры

```bash
python manage.py sync_clusters
```

### 4. Проверить в Django Admin

```bash
python manage.py createsuperuser
python manage.py runserver

# Открыть http://localhost:8000/admin/
# Databases → Clusters
```

---

## 🔍 Troubleshooting

### gRPC connection refused

```python
# Проверить что cluster-service запущен
import grpc

channel = grpc.insecure_channel('localhost:50051')
try:
    grpc.channel_ready_future(channel).result(timeout=5)
    print("✅ cluster-service is running")
except grpc.FutureTimeoutError:
    print("❌ cluster-service is not running")
```

### Sync не находит кластеры

1. Проверить что RAS запущен (порт 1545)
2. Проверить что ras-grpc-gw запущен (порт 9999)
3. Проверить логи cluster-service

```bash
# Логи cluster-service
docker compose logs cluster-service

# Health check cluster-service
curl http://localhost:8088/health
```

### Модели не отображаются в Admin

```python
# Убедиться что app зарегистрирован
# settings.py
INSTALLED_APPS = [
    ...
    'apps.databases',
]
```

---

## 📊 Производительность

**Текущие метрики:**
- Sync 1 кластера: ~50ms
- Sync 10 кластеров: ~500ms
- Sync 3 infobases: ~100ms

**Оптимизация (Phase 2):**
- Кэширование gRPC соединений
- Batch запросы
- Асинхронная синхронизация через Celery

---

## 📚 Справочная информация

### Детальная документация (архив)

Для глубокого погружения см. `docs/archive/django_cluster_sync/`:
- `DJANGO_CLUSTER_SYNC.md` - общая концепция
- `CLUSTER_SERVICE_IMPLEMENTATION.md` - детали gRPC клиента
- `CLUSTER_SYNC_IMPLEMENTATION.md` - синхронизация моделей
- `CLUSTER_SYNC_SUMMARY.md` - краткое резюме

### Полезные ссылки

- [cluster-service README](../go-services/cluster-service/README.md) - gRPC сервис
- [Django gRPC](https://github.com/grpc/grpc/tree/master/examples/python) - примеры
- [1C_ADMINISTRATION_GUIDE.md](./1C_ADMINISTRATION_GUIDE.md) - RAS/RAC гайд

---

## ✅ Next Steps (Phase 2)

- [ ] Автоматическая синхронизация через Celery (каждые 5 минут)
- [ ] WebSocket streaming для real-time обновлений
- [ ] Метрики синхронизации (Prometheus)
- [ ] Retry logic для failed syncs

---

**Версия:** 1.0
**Последнее обновление:** 2025-10-31
**Автор:** Architecture Team

**См. также:**
- `docs/1C_ADMINISTRATION_GUIDE.md` - работа с RAS/RAC
- `docs/SPRINT_1_PROGRESS.md` - Sprint 1 история
- `orchestrator/apps/databases/README_SERVICES.md` - services layer
