# CommandCenter1C Monorepo - Детальная структура

## Root Structure

```
command-center-1c/
├── go-services/              # Go микросервисы
├── orchestrator/             # Python/Django backend
├── frontend/                 # React frontend
├── infrastructure/           # Docker, K8s, monitoring configs
├── docs/                     # Документация
├── scripts/                  # Dev/deployment scripts
├── .claude/                  # AI skills и commands
├── docker-compose.yml        # Local development
├── docker-compose.local.yml  # Infrastructure only
├── Makefile                  # Build система
└── README.md                 # Main README

```

---

## go-services/ - Go Микросервисы

```
go-services/
├── api-gateway/             # HTTP router, auth, rate limiting
│   ├── cmd/main.go          # Entry point
│   ├── internal/
│   │   ├── handlers/        # HTTP handlers
│   │   ├── middleware/      # JWT auth, rate limit, logging
│   │   └── router/          # Gin router setup
│   ├── config/              # Configuration
│   └── go.mod
│
├── worker/                  # Parallel task processing
│   ├── cmd/main.go
│   ├── internal/
│   │   ├── worker/          # Goroutine pool
│   │   ├── tasks/           # Task handlers
│   │   └── odata/           # OData client
│   └── go.mod
│
├── cluster-service/         # 1C cluster management (RAS/gRPC)
│   ├── cmd/main.go
│   ├── internal/
│   │   ├── handlers/        # HTTP handlers
│   │   ├── grpc/            # gRPC client для ras-grpc-gw
│   │   └── models/          # Cluster, Infobase models
│   └── go.mod
│
├── batch-service/           # Batch operations (в разработке)
│   ├── cmd/main.go
│   ├── internal/
│   │   ├── handlers/
│   │   ├── batch/           # Batch execution logic
│   │   └── subprocess/      # 1cv8.exe wrapper
│   └── go.mod
│
└── shared/                  # Общий код для всех Go сервисов
    ├── auth/                # JWT validation
    ├── config/              # Config loading (env vars)
    ├── logger/              # Structured logging (zerolog)
    ├── metrics/             # Prometheus metrics
    └── models/              # Shared data models
```

### Naming Convention для Go бинарников

**Формат:** `cc1c-<service-name>.exe` (Windows) / `cc1c-<service-name>` (Linux)

**Примеры:**
```
bin/cc1c-api-gateway.exe
bin/cc1c-worker.exe
bin/cc1c-cluster-service.exe
bin/cc1c-batch-service.exe
```

**Сборка:**
```bash
make build-go-all           # Все сервисы
make build-api-gateway      # Отдельный сервис
./scripts/build.sh --parallel  # Параллельная сборка
```

---

## orchestrator/ - Django Backend

```
orchestrator/
├── apps/                    # Django apps
│   ├── databases/           # Database CRUD, OData, health checks
│   │   ├── models.py        # Database, DatabaseCredentials
│   │   ├── views.py         # DRF ViewSets
│   │   ├── serializers.py   # DRF Serializers
│   │   ├── odata_adapter.py # OneCODataAdapter
│   │   └── tasks.py         # Celery tasks
│   │
│   ├── operations/          # Operation management
│   │   ├── models.py        # Operation, OperationHistory
│   │   ├── views.py         # Execute operation endpoint
│   │   └── tasks.py         # Operation execution tasks
│   │
│   └── templates/           # Template engine
│       ├── models.py        # OperationTemplate
│       ├── renderer.py      # Jinja2 template rendering
│       └── validators.py    # Template validation
│
├── config/                  # Django settings
│   ├── settings/
│   │   ├── base.py          # Common settings
│   │   ├── local.py         # Local development
│   │   └── production.py    # Production settings
│   ├── urls.py              # URL routing
│   └── celery.py            # Celery configuration
│
├── manage.py                # Django management script
├── requirements.txt         # Python dependencies
└── pytest.ini               # Pytest configuration
```

### Django Apps Architecture

**databases:**
- **Responsibility:** Управление метаданными 1С баз
- **Endpoints:** CRUD operations для Database model
- **External Calls:** OData requests к 1С базам

**operations:**
- **Responsibility:** Выполнение операций над 1С базами
- **Endpoints:** POST /api/operations/execute
- **External Calls:** Enqueue Celery tasks

**templates:**
- **Responsibility:** Шаблонизация операций
- **Logic:** Render Jinja2 templates с параметрами
- **Validation:** Check template syntax перед execution

---

## frontend/ - React Frontend

```
frontend/
├── src/
│   ├── api/                 # API client
│   │   ├── client.ts        # Axios instance
│   │   ├── databases.ts     # Database API calls
│   │   └── operations.ts    # Operation API calls
│   │
│   ├── components/          # UI components
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Footer.tsx
│   │   ├── databases/
│   │   │   ├── DatabaseList.tsx
│   │   │   └── DatabaseForm.tsx
│   │   └── operations/
│   │       ├── OperationList.tsx
│   │       └── OperationExecuteForm.tsx
│   │
│   ├── pages/               # App pages
│   │   ├── Dashboard.tsx
│   │   ├── Databases.tsx
│   │   ├── Operations.tsx
│   │   └── Monitoring.tsx
│   │
│   ├── stores/              # State management (Zustand)
│   │   ├── authStore.ts
│   │   ├── databaseStore.ts
│   │   └── operationStore.ts
│   │
│   ├── utils/               # Utilities
│   │   ├── formatters.ts
│   │   └── validators.ts
│   │
│   ├── App.tsx              # Main app component
│   └── main.tsx             # Entry point
│
├── public/                  # Static assets
├── package.json
├── tsconfig.json
└── vite.config.ts           # Vite configuration
```

---

## infrastructure/ - Docker, K8s, Monitoring

```
infrastructure/
├── docker/                  # Dockerfiles
│   ├── api-gateway.Dockerfile
│   ├── worker.Dockerfile
│   ├── orchestrator.Dockerfile
│   └── frontend.Dockerfile
│
├── k8s/                     # Kubernetes manifests (для production)
│   ├── base/                # Base manifests
│   │   ├── api-gateway.yaml
│   │   ├── worker.yaml
│   │   └── orchestrator.yaml
│   │
│   └── overlays/            # Kustomize overlays
│       ├── development/
│       ├── staging/
│       └── production/
│
├── monitoring/              # Prometheus + Grafana
│   ├── prometheus/
│   │   ├── prometheus.yml   # Prometheus config
│   │   └── alerts.yml       # Alert rules
│   │
│   └── grafana/
│       ├── dashboards/
│       │   ├── overview.json
│       │   ├── operations.json
│       │   └── performance.json
│       └── datasources.yml
│
└── terraform/               # IaC (planned)
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

---

## docs/ - Документация

```
docs/
├── ROADMAP.md               # Balanced Approach roadmap
├── START_HERE.md            # Быстрый старт
├── EXECUTIVE_SUMMARY.md     # Краткое резюме
├── LOCAL_DEVELOPMENT_GUIDE.md  # Полное руководство
├── 1C_ADMINISTRATION_GUIDE.md  # RAS/RAC, gRPC
├── DJANGO_CLUSTER_INTEGRATION.md  # cluster-service ↔ Django
├── ODATA_INTEGRATION.md     # OData best practices
│
├── architecture/            # Архитектурные решения
│   ├── adr-001-monorepo.md
│   ├── adr-002-go-workers.md
│   └── adr-003-django-orchestrator.md
│
├── api/                     # API спецификация
│   ├── openapi.yaml         # OpenAPI 3.0 spec
│   └── endpoints.md         # Endpoint documentation
│
├── deployment/              # Развертывание
│   ├── local.md
│   ├── docker.md
│   └── kubernetes.md
│
└── archive/                 # Архив
    ├── sprints/
    │   ├── sprint-1.1-summary.md
    │   ├── sprint-1.2-summary.md
    │   └── ...
    └── roadmap_variants/
        ├── MVP_FIRST.md
        └── ENTERPRISE_GRADE.md
```

---

## scripts/ - Dev/Deployment Scripts

```
scripts/
├── dev/                     # Local development
│   ├── start-all.sh         # Запустить все сервисы
│   ├── stop-all.sh          # Остановить все
│   ├── restart.sh           # Перезапустить сервис
│   ├── health-check.sh      # Проверить health checks
│   ├── logs.sh              # Просмотр логов
│   └── build-and-start.sh   # Собрать + запустить
│
├── build.sh                 # Сборка Go бинарников
├── test-all.sh              # Запуск всех тестов
└── deploy/                  # Deployment scripts (planned)
    ├── docker-deploy.sh
    └── k8s-deploy.sh
```

---

## .claude/ - AI Skills & Commands

```
.claude/
├── skills/                  # AI skills для Claude
│   ├── cc1c-devops/
│   ├── cc1c-navigator/
│   ├── cc1c-odata-integration/
│   ├── cc1c-service-builder/
│   ├── cc1c-sprint-guide/
│   └── cc1c-test-runner/
│
└── commands/                # Slash commands
    ├── dev-start.md
    ├── check-health.md
    ├── restart-service.md
    ├── run-migrations.md
    ├── test-all.md
    └── build-docker.md
```

---

## Ключевые файлы

### Configuration Files

**Environment:**
- `.env.local` - Local development env vars
- `.env.example` - Example env vars (checked in)

**Docker:**
- `docker-compose.yml` - Full stack (11 services)
- `docker-compose.local.yml` - Infrastructure only (postgres, redis)

**Build:**
- `Makefile` - Build система для Go services
- `scripts/build.sh` - Централизованная сборка

### Process Management

**PID files:**
```
pids/
├── orchestrator.pid
├── celery-worker.pid
├── api-gateway.pid
├── worker-1.pid
└── frontend.pid
```

**Log files:**
```
logs/
├── orchestrator.log
├── celery-worker.log
├── api-gateway.log
└── frontend.log
```

---

## File Naming Conventions

**Go files:**
- `main.go` - Entry point
- `*_handler.go` - HTTP handlers
- `*_service.go` - Business logic
- `*_repository.go` - Data access
- `*_test.go` - Tests

**Python files:**
- `models.py` - Django models
- `views.py` - DRF ViewSets
- `serializers.py` - DRF Serializers
- `tasks.py` - Celery tasks
- `test_*.py` - Tests

**React files:**
- `*.tsx` - TypeScript + JSX components
- `*.ts` - TypeScript utilities
- `*.test.tsx` - Component tests

---

## Import Patterns

### Go imports

```go
import (
    // Standard library
    "context"
    "fmt"

    // Third-party
    "github.com/gin-gonic/gin"

    // Internal
    "github.com/yourusername/command-center-1c/go-services/shared/logger"
    "github.com/yourusername/command-center-1c/go-services/api-gateway/internal/handlers"
)
```

### Python imports

```python
# Standard library
import os
import logging

# Third-party
from django.db import models
from rest_framework import viewsets

# Local app
from .models import Database
from .serializers import DatabaseSerializer
```

### React imports

```typescript
// React
import React, { useState, useEffect } from 'react';

// Third-party
import { Button, Table } from 'antd';

// Internal
import { getDatabases } from '../api/databases';
import { useDatabaseStore } from '../stores/databaseStore';
```

---

## См. также

- `service-dependencies.md` - Граф зависимостей между сервисами
- `docs/START_HERE.md` - Быстрый старт по документации
- `CLAUDE.md` - Главный файл инструкций для AI
