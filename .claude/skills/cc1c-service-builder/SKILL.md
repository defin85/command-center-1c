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
- Добавление нового API endpoint (Go/Django)
- Создание нового Django app
- Создание нового Go service
- Добавление нового React компонента (page, form, component)
- Пользователь упоминает: create, add, new, implement, build, scaffold

## Key Conventions

### 1. Code Organization

- **Go services** → `go-services/<service-name>/`
- **Go shared** → `go-services/shared/` (если используется в 2+ сервисах)
- **Django apps** → `orchestrator/apps/<app-name>/`
- **React components** → `frontend/src/components/` or `frontend/src/pages/`

### 2. Naming Conventions

```
Go:
- Handlers: NewOperationHandler, HandleListOperations
- Services: OperationService, ProcessOperation
- Interfaces: Processor, Repository
- Files: operation_handler.go, operation_service.go

Django:
- Models: Operation, Database (PascalCase)
- ViewSets: OperationViewSet
- Serializers: OperationSerializer
- Services: OperationService
- Files: models.py, views.py, serializers.py, services.py

React:
- Components: OperationForm, OperationList (PascalCase)
- Files: OperationForm.tsx, OperationList.tsx
- Tests: OperationForm.test.tsx
```

### 3. Testing Requirements

**⚠️ ОБЯЗАТЕЛЬНО:** Coverage > 70% для всего нового кода!

- Go: table-driven tests, `_test.go` файлы
- Django: pytest, model/view/service tests
- React: React Testing Library, component tests

## Go Service Patterns

### Create API Endpoint (API Gateway)

**Файлы:**
```
go-services/api-gateway/internal/handlers/
├── your_handler.go
└── your_handler_test.go

go-services/api-gateway/internal/router/
└── router.go  # Add route here
```

**Quick Start:**
```go
// handlers/your_handler.go
package handlers

import (
    "net/http"
    "github.com/gin-gonic/gin"
)

type YourHandler struct {
    log logger.Logger
}

func NewYourHandler(log logger.Logger) *YourHandler {
    return &YourHandler{log: log}
}

func (h *YourHandler) HandleEndpoint(c *gin.Context) {
    c.JSON(http.StatusOK, gin.H{"status": "success"})
}

// router.go
api.POST("/your-endpoint", handlers.Your.HandleEndpoint)
```

**Детали:** {baseDir}/reference/go-patterns.md
**Template:** {baseDir}/templates/go-handler.go.tmpl

### Create Worker Processor

**Pattern:** Goroutines pool + semaphore для контроля concurrency

```go
func (p *Processor) Process(ctx context.Context, tasks []Task) error {
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
```

**Детали:** {baseDir}/reference/go-patterns.md

## Django App Patterns

### Create New Django App

**Команда:**
```bash
cd orchestrator
python manage.py startapp your_app apps/your_app
```

**Структура:**
```
apps/your_app/
├── models.py          # Database models
├── views.py           # DRF ViewSets
├── serializers.py     # DRF Serializers
├── services.py        # Business logic (создай вручную)
├── tasks.py           # Celery tasks (опционально)
├── urls.py            # URL routing
├── admin.py           # Django admin
└── tests/
    ├── test_models.py
    ├── test_views.py
    └── test_services.py
```

**Регистрация в settings.py:**
```python
INSTALLED_APPS = [
    ...
    'apps.your_app',
]
```

**Детали:** {baseDir}/reference/django-patterns.md
**Template:** {baseDir}/templates/django-viewset.py.tmpl

### Create DRF ViewSet

```python
# views.py
from rest_framework import viewsets
from .models import YourModel
from .serializers import YourModelSerializer
from .services import YourService

class YourModelViewSet(viewsets.ModelViewSet):
    queryset = YourModel.objects.all()
    serializer_class = YourModelSerializer

    def create(self, request, *args, **kwargs):
        service = YourService()
        result = service.create_item(request.data)
        serializer = self.get_serializer(result)
        return Response(serializer.data, status=201)
```

**Детали:** {baseDir}/reference/django-patterns.md

## React Component Patterns

### Create React Component

**Файлы:**
```
frontend/src/components/
├── YourComponent.tsx
└── YourComponent.test.tsx

frontend/src/pages/
├── YourPage.tsx
└── YourPage.test.tsx
```

**Pattern:**
```typescript
// YourComponent.tsx
import React from 'react';
import { Button, Form } from 'antd';

interface YourComponentProps {
  onSubmit: (data: any) => void;
}

const YourComponent: React.FC<YourComponentProps> = ({ onSubmit }) => {
  const [form] = Form.useForm();

  const handleSubmit = (values: any) => {
    onSubmit(values);
  };

  return (
    <Form form={form} onFinish={handleSubmit}>
      {/* Form fields */}
      <Button type="primary" htmlType="submit">Submit</Button>
    </Form>
  );
};

export default YourComponent;
```

**Детали:** {baseDir}/reference/react-patterns.md
**Template:** {baseDir}/templates/react-component.tsx.tmpl

## Critical Constraints

1. **Naming:** Следуй project naming conventions (см. выше)
2. **Structure:** Размещай файлы в правильных директориях
3. **Testing:** Coverage > 70% обязательно
4. **Dependencies:** Go shared для переиспользуемого кода, НЕ дублируй
5. **Documentation:** Добавляй docstrings/comments для публичных функций

## Common Operations

### Create Go API Endpoint

1. Создай handler в `internal/handlers/your_handler.go`
2. Добавь route в `internal/router/router.go`
3. Напиши тест в `internal/handlers/your_handler_test.go`
4. Проверь coverage: `go test -cover ./internal/handlers`

### Create Django App

1. `python manage.py startapp your_app apps/your_app`
2. Добавь в `INSTALLED_APPS` в settings.py
3. Создай models.py, views.py, serializers.py, services.py
4. Создай migrations: `python manage.py makemigrations`
5. Напиши тесты в `tests/`
6. Зарегистрируй URLs в `orchestrator/config/urls.py`

### Create React Component

1. Создай `YourComponent.tsx` в `components/` или `pages/`
2. Создай `YourComponent.test.tsx` рядом
3. Если нужен API - создай endpoint в `api/endpoints/`
4. Если нужен state - создай store в `stores/`
5. Запусти тесты: `npm test -- YourComponent.test.tsx`

## References

### Detailed Patterns
- {baseDir}/reference/go-patterns.md - Go service patterns, worker patterns
- {baseDir}/reference/django-patterns.md - Django models, ViewSets, services
- {baseDir}/reference/react-patterns.md - React components, hooks, stores

### Code Templates
- {baseDir}/templates/go-handler.go.tmpl - Go HTTP handler template
- {baseDir}/templates/django-viewset.py.tmpl - Django ViewSet template
- {baseDir}/templates/react-component.tsx.tmpl - React component template

### Related Skills
- `cc1c-test-runner` - для запуска тестов после создания кода
- `cc1c-navigator` - для понимания где размещать новый код
- `cc1c-devops` - для запуска/проверки нового сервиса

### Project Documentation
- [CLAUDE.md](../../../CLAUDE.md) - Project structure, conventions
- [Architecture docs](../../../docs/architecture/) - Architectural patterns

---

**Version:** 2.0 (Optimized)
**Last Updated:** 2025-11-06
**Changelog:**
- 2.0 (2025-11-06): Refactored to 200 lines, moved details to reference/ and templates/
- 1.0 (2025-01-17): Initial release with Go/Django/React patterns
