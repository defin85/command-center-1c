---
name: cc1c-service-builder
description: "Create Go services, Django apps, or React components following project conventions. Generates code from templates. Use when adding new functionality, endpoints, or UI components."
allowed-tools: ["Read", "Write", "Edit", "Glob"]
---

# cc1c-service-builder

## Purpose

Создавать новые компоненты проекта CommandCenter1C следуя установленным конвенциям, шаблонам и best practices. Обеспечивать консистентность кодовой базы.

## When to Use

Используй этот skill когда:
- Пользователь хочет добавить новый endpoint
- Нужно создать новый Django app
- Требуется создать новый Go service
- Надо добавить новый React компонент (page, form, etc.)
- Пользователь упоминает: create, add, new, implement, build

## Project Conventions

### Commit Message Format

```
[component] Короткое описание

Детальное описание (опционально)

Примеры:
[api-gateway] Add JWT authentication middleware
[orchestrator] Implement template validation logic
[frontend] Create operation execution form
[worker] Add parallel processing for bulk operations
[infra] Add Kubernetes deployment manifests
[docs] Update API documentation
```

### Code Organization Principles

1. **Separation of Concerns** - каждый компонент делает одну вещь хорошо
2. **DRY** - не дублируй код, используй shared libraries
3. **Convention over Configuration** - следуй принятым паттернам
4. **Testing** - coverage > 70% обязательно

## Go Service Templates

### 1. Creating New API Endpoint (API Gateway)

**Структура:**
```
go-services/api-gateway/internal/handlers/
├── operations.go        # Existing
└── your_new_handler.go  # New
```

**Template:** См. `templates/go-service.go.template`

**Шаги:**
1. Создай handler в `internal/handlers/your_handler.go`
2. Добавь route в `internal/router/router.go`
3. Если нужна middleware - добавь в `internal/middleware/`
4. Напиши unit test в `internal/handlers/your_handler_test.go`

**Пример handler:**
```go
package handlers

import (
    "net/http"
    "github.com/gin-gonic/gin"
    "command-center/go-services/shared/logger"
)

type YourHandler struct {
    log logger.Logger
}

func NewYourHandler(log logger.Logger) *YourHandler {
    return &YourHandler{log: log}
}

// HandleYourEndpoint handles your specific endpoint
func (h *YourHandler) HandleYourEndpoint(c *gin.Context) {
    h.log.Info("Processing request", "path", c.Request.URL.Path)

    // Your logic here

    c.JSON(http.StatusOK, gin.H{
        "status": "success",
        "data": nil,
    })
}
```

**Регистрация route:**
```go
// internal/router/router.go
func SetupRouter(handlers *Handlers) *gin.Engine {
    router := gin.Default()

    api := router.Group("/api")
    {
        api.POST("/your-endpoint", handlers.Your.HandleYourEndpoint)
    }

    return router
}
```

### 2. Creating New Worker Type

**Структура:**
```
go-services/worker/internal/processor/
├── operation_processor.go  # Existing
└── your_processor.go        # New
```

**Ключевые аспекты:**
- Используй goroutines pool для параллелизма
- Контролируй количество одновременных workers через semaphore
- Логируй прогресс и ошибки
- Возвращай детальные результаты в Redis

**Пример processor:**
```go
package processor

import (
    "context"
    "sync"
)

type YourProcessor struct {
    maxConcurrent int
}

func NewYourProcessor(maxConcurrent int) *YourProcessor {
    return &YourProcessor{
        maxConcurrent: maxConcurrent,
    }
}

func (p *YourProcessor) Process(ctx context.Context, tasks []Task) error {
    sem := make(chan struct{}, p.maxConcurrent)
    var wg sync.WaitGroup

    for _, task := range tasks {
        wg.Add(1)
        go func(t Task) {
            defer wg.Done()
            sem <- struct{}{}        // acquire
            defer func() { <-sem }() // release

            p.processTask(ctx, t)
        }(task)
    }

    wg.Wait()
    return nil
}

func (p *YourProcessor) processTask(ctx context.Context, task Task) error {
    // Your processing logic here
    return nil
}
```

### 3. Shared Library Component

**Когда создавать в shared/:**
- Код используется в 2+ сервисах
- Общая бизнес-логика (auth, logging, metrics)
- Shared models/structs

**Структура:**
```
go-services/shared/
├── auth/
├── logger/
├── metrics/
├── models/
└── your_package/   # New
    ├── interface.go
    ├── implementation.go
    └── implementation_test.go
```

## Django App Templates

### 1. Creating New Django App

**Шаги:**
```bash
cd orchestrator
python manage.py startapp your_app_name apps/your_app_name
```

**Структура:**
```
orchestrator/apps/your_app_name/
├── __init__.py
├── models.py          # Database models
├── views.py           # DRF ViewSets
├── serializers.py     # DRF Serializers
├── services.py        # Business logic (создай вручную)
├── tasks.py           # Celery tasks (создай вручную)
├── admin.py           # Django admin
├── urls.py            # URL routing
├── tests/             # Tests
│   ├── test_models.py
│   ├── test_views.py
│   └── test_services.py
└── migrations/
```

**Template:** См. `templates/django-app.py.template`

### 2. Django Model Example

```python
# apps/your_app/models.py
from django.db import models
from django.utils import timezone

class YourModel(models.Model):
    """
    Описание модели
    """
    name = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Your Model"
        verbose_name_plural = "Your Models"
        ordering = ['-created_at']
        db_table = 'your_app_yourmodel'

    def __str__(self):
        return self.name
```

### 3. DRF ViewSet Example

```python
# apps/your_app/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import YourModel
from .serializers import YourModelSerializer
from .services import YourService

class YourModelViewSet(viewsets.ModelViewSet):
    """
    API endpoints для YourModel

    list: Получить список
    create: Создать новый
    retrieve: Получить по ID
    update: Обновить
    destroy: Удалить
    """
    queryset = YourModel.objects.all()
    serializer_class = YourModelSerializer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = YourService()

    def create(self, request, *args, **kwargs):
        """Создание через service layer"""
        result = self.service.create_item(request.data)
        serializer = self.get_serializer(result)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def custom_action(self, request, pk=None):
        """Кастомный endpoint"""
        obj = self.get_object()
        # Your logic here
        return Response({'status': 'success'})
```

### 4. DRF Serializer Example

```python
# apps/your_app/serializers.py
from rest_framework import serializers
from .models import YourModel

class YourModelSerializer(serializers.ModelSerializer):
    """Serializer для YourModel"""

    class Meta:
        model = YourModel
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        """Custom validation"""
        if len(value) < 3:
            raise serializers.ValidationError("Название должно быть минимум 3 символа")
        return value
```

### 5. Service Layer Example

```python
# apps/your_app/services.py
from django.db import transaction
from .models import YourModel
import logging

logger = logging.getLogger(__name__)

class YourService:
    """
    Business logic для YourModel
    Разделение: Views получают requests, Services обрабатывают бизнес-логику
    """

    @transaction.atomic
    def create_item(self, data: dict) -> YourModel:
        """
        Создает новый item с валидацией
        """
        logger.info(f"Creating item with data: {data}")

        # Business logic here
        item = YourModel.objects.create(**data)

        # Trigger async task if needed
        # from .tasks import process_item_task
        # process_item_task.delay(item.id)

        return item

    def get_active_items(self):
        """Получить только активные"""
        return YourModel.objects.filter(is_active=True)
```

### 6. Celery Task Example

```python
# apps/your_app/tasks.py
from celery import shared_task
from .models import YourModel
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_item_task(self, item_id: int):
    """
    Асинхронная обработка item

    Args:
        item_id: ID объекта YourModel
    """
    try:
        item = YourModel.objects.get(id=item_id)
        logger.info(f"Processing item {item_id}")

        # Your async logic here

        logger.info(f"Item {item_id} processed successfully")
        return {'status': 'success', 'item_id': item_id}

    except YourModel.DoesNotExist:
        logger.error(f"Item {item_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Error processing item {item_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
```

### 7. URL Configuration

```python
# apps/your_app/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import YourModelViewSet

router = DefaultRouter()
router.register(r'items', YourModelViewSet, basename='yourmodel')

urlpatterns = [
    path('', include(router.urls)),
]
```

**Подключение в главный urls.py:**
```python
# orchestrator/config/urls.py
urlpatterns = [
    path('api/your-app/', include('apps.your_app.urls')),
]
```

### 8. Django Admin

```python
# apps/your_app/admin.py
from django.contrib import admin
from .models import YourModel

@admin.register(YourModel)
class YourModelAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
```

## React Component Templates

### 1. Creating New Page Component

**Структура:**
```
frontend/src/pages/YourPage/
├── index.tsx           # Main page component
├── components/         # Page-specific components
│   ├── YourForm.tsx
│   └── YourTable.tsx
└── styles.module.css   # CSS modules (optional)
```

**Template:** См. `templates/react-component.tsx.template`

### 2. Page Component Example

```typescript
// frontend/src/pages/YourPage/index.tsx
import React, { useEffect, useState } from 'react';
import { Card, Button, message } from 'antd';
import { useYourData } from '../../stores/useYourData';
import YourTable from './components/YourTable';
import YourForm from './components/YourForm';

const YourPage: React.FC = () => {
  const { data, loading, fetchData, createItem } = useYourData();
  const [isFormVisible, setIsFormVisible] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreate = async (values: any) => {
    try {
      await createItem(values);
      message.success('Создано успешно');
      setIsFormVisible(false);
      fetchData();
    } catch (error) {
      message.error('Ошибка при создании');
    }
  };

  return (
    <div>
      <Card
        title="Your Page Title"
        extra={
          <Button type="primary" onClick={() => setIsFormVisible(true)}>
            Создать
          </Button>
        }
      >
        <YourTable data={data} loading={loading} />
      </Card>

      <YourForm
        visible={isFormVisible}
        onCancel={() => setIsFormVisible(false)}
        onSubmit={handleCreate}
      />
    </div>
  );
};

export default YourPage;
```

### 3. Form Component Example

```typescript
// frontend/src/pages/YourPage/components/YourForm.tsx
import React from 'react';
import { Modal, Form, Input, Switch } from 'antd';

interface YourFormProps {
  visible: boolean;
  onCancel: () => void;
  onSubmit: (values: any) => void;
  initialValues?: any;
}

const YourForm: React.FC<YourFormProps> = ({
  visible,
  onCancel,
  onSubmit,
  initialValues
}) => {
  const [form] = Form.useForm();

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      onSubmit(values);
      form.resetFields();
    } catch (error) {
      console.error('Validation failed:', error);
    }
  };

  return (
    <Modal
      title="Создать/Редактировать"
      open={visible}
      onCancel={onCancel}
      onOk={handleSubmit}
      okText="Сохранить"
      cancelText="Отмена"
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={initialValues}
      >
        <Form.Item
          name="name"
          label="Название"
          rules={[
            { required: true, message: 'Введите название' },
            { min: 3, message: 'Минимум 3 символа' }
          ]}
        >
          <Input placeholder="Введите название" />
        </Form.Item>

        <Form.Item
          name="description"
          label="Описание"
        >
          <Input.TextArea rows={4} placeholder="Введите описание" />
        </Form.Item>

        <Form.Item
          name="isActive"
          label="Активен"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default YourForm;
```

### 4. API Client Example

```typescript
// frontend/src/api/endpoints/yourEndpoint.ts
import { apiClient } from '../client';

export interface YourItem {
  id: number;
  name: string;
  description: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface CreateYourItemRequest {
  name: string;
  description?: string;
  isActive?: boolean;
}

export const yourEndpointApi = {
  getAll: async (): Promise<YourItem[]> => {
    const response = await apiClient.get('/your-endpoint/items/');
    return response.data;
  },

  getById: async (id: number): Promise<YourItem> => {
    const response = await apiClient.get(`/your-endpoint/items/${id}/`);
    return response.data;
  },

  create: async (data: CreateYourItemRequest): Promise<YourItem> => {
    const response = await apiClient.post('/your-endpoint/items/', data);
    return response.data;
  },

  update: async (id: number, data: Partial<CreateYourItemRequest>): Promise<YourItem> => {
    const response = await apiClient.patch(`/your-endpoint/items/${id}/`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/your-endpoint/items/${id}/`);
  },

  customAction: async (id: number): Promise<any> => {
    const response = await apiClient.post(`/your-endpoint/items/${id}/custom_action/`);
    return response.data;
  }
};
```

### 5. State Management (Zustand) Example

```typescript
// frontend/src/stores/useYourData.ts
import { create } from 'zustand';
import { yourEndpointApi, YourItem, CreateYourItemRequest } from '../api/endpoints/yourEndpoint';

interface YourDataState {
  data: YourItem[];
  loading: boolean;
  error: string | null;
  fetchData: () => Promise<void>;
  createItem: (data: CreateYourItemRequest) => Promise<void>;
  updateItem: (id: number, data: Partial<CreateYourItemRequest>) => Promise<void>;
  deleteItem: (id: number) => Promise<void>;
}

export const useYourData = create<YourDataState>((set) => ({
  data: [],
  loading: false,
  error: null,

  fetchData: async () => {
    set({ loading: true, error: null });
    try {
      const data = await yourEndpointApi.getAll();
      set({ data, loading: false });
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  createItem: async (itemData) => {
    set({ loading: true, error: null });
    try {
      const newItem = await yourEndpointApi.create(itemData);
      set((state) => ({
        data: [...state.data, newItem],
        loading: false
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  updateItem: async (id, itemData) => {
    set({ loading: true, error: null });
    try {
      const updatedItem = await yourEndpointApi.update(id, itemData);
      set((state) => ({
        data: state.data.map((item) =>
          item.id === id ? updatedItem : item
        ),
        loading: false
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  deleteItem: async (id) => {
    set({ loading: true, error: null });
    try {
      await yourEndpointApi.delete(id);
      set((state) => ({
        data: state.data.filter((item) => item.id !== id),
        loading: false
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
      throw error;
    }
  }
}));
```

## Testing Templates

### Go Test Example

```go
// internal/handlers/your_handler_test.go
package handlers

import (
    "net/http"
    "net/http/httptest"
    "testing"
    "github.com/gin-gonic/gin"
    "github.com/stretchr/testify/assert"
)

func TestYourHandler_HandleYourEndpoint(t *testing.T) {
    gin.SetMode(gin.TestMode)

    tests := []struct {
        name           string
        expectedStatus int
    }{
        {
            name:           "Success case",
            expectedStatus: http.StatusOK,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            w := httptest.NewRecorder()
            c, _ := gin.CreateTestContext(w)

            handler := NewYourHandler(mockLogger)
            handler.HandleYourEndpoint(c)

            assert.Equal(t, tt.expectedStatus, w.Code)
        })
    }
}
```

### Django Test Example

```python
# apps/your_app/tests/test_views.py
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.your_app.models import YourModel

class YourModelViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.item = YourModel.objects.create(
            name="Test Item",
            description="Test Description"
        )

    def test_list_items(self):
        """Тест получения списка"""
        response = self.client.get('/api/your-app/items/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_item(self):
        """Тест создания"""
        data = {
            'name': 'New Item',
            'description': 'New Description'
        }
        response = self.client.post('/api/your-app/items/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(YourModel.objects.count(), 2)
```

## Checklist for New Component

**Go Service:**
- [ ] Handler/Processor реализован
- [ ] Route зарегистрирован (если нужно)
- [ ] Unit tests написаны
- [ ] Shared code переиспользован (auth, logger, metrics)
- [ ] Error handling добавлен
- [ ] Logging добавлен

**Django App:**
- [ ] Models определены с verbose_name
- [ ] Serializers созданы
- [ ] Views (ViewSets) реализованы
- [ ] Service layer создан для бизнес-логики
- [ ] Celery tasks добавлены (если нужны)
- [ ] URLs зарегистрированы
- [ ] Admin panel настроен
- [ ] Tests написаны (models, views, services)
- [ ] Migrations созданы

**React Component:**
- [ ] Component реализован
- [ ] API client создан
- [ ] State management настроен
- [ ] Form validation добавлена
- [ ] Error handling добавлен
- [ ] Loading states обработаны
- [ ] TypeScript types определены

**General:**
- [ ] Code review checklist пройден
- [ ] Documentation обновлена
- [ ] Commit message соответствует формату
- [ ] Coverage > 70%

## References

- Templates: `.claude/skills/cc1c-service-builder/templates/`
- Project conventions: `CLAUDE.md`
- Architecture overview: `docs/ROADMAP.md`
- Testing strategy: `CLAUDE.md` - Testing Strategy section

## Related Skills

После создания компонента используй:
- `cc1c-test-runner` - для запуска тестов нового компонента
- `cc1c-navigator` - для проверки структуры и расположения
- `cc1c-devops` - для deployment и тестирования в окружении
- `cc1c-odata-integration` - если компонент работает с 1С

---

**Version:** 1.0
**Last Updated:** 2025-01-17
**Changelog:**
- 1.0 (2025-01-17): Initial release with templates for Go, Django, React
