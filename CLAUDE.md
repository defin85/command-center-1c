# CommandCenter1C - Инструкции для AI агентов

> Микросервисная платформа для централизованного управления 700+ базами 1С

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО

**🎯 ВЫБРАННЫЙ ВАРИАНТ: Balanced Approach (14-16 недель)**

- В документации описаны три варианта (MVP, Balanced, Enterprise) для справки
- **Реализация ведется ТОЛЬКО по варианту Balanced**
- Фокус: Phases 1-5 из Balanced roadmap (см. `docs/ROADMAP.md`)

**Текущая фаза:** Phase 1, Week 3-4 (Core Functionality)
**Статус:** ✅ Sprint 1.4 завершен - cluster-service интеграция с RAS

---

## 🎯 О проекте

**Цель:** Платформа для массовых операций с данными в 700+ базах 1С:Бухгалтерия 3.0 с параллельной обработкой и real-time мониторингом.

**Экономия:** 10-100x ускорение операций, ROI 260-1200% в первый год.

---

## 🏗️ Архитектура

```
┌─────────┐
│ React   │ TypeScript + Ant Design
│ (3000)  │
└────┬────┘
     │ HTTP + WebSocket
┌────▼────┐
│ Go API  │ Gin + JWT + Rate Limiting
│ Gateway │
│ (8080)  │
└────┬────┘
     │ HTTP
┌────▼────────┐
│ Django      │ DRF + Celery
│ Orchestr.   │ Business Logic
│ (8000)      │
└──┬────┬─────┘
   │    │
┌──▼──┐ │  ┌──────────┐
│Redis│ └─→│PostgreSQL│
│Queue│    │ (5432)   │
└──┬──┘    └──────────┘
   │
┌──▼──────┐
│Go Worker│ Goroutines pool (x2 replicas)
│Pool     │ Parallel: 100-500 bases
└────┬────┘
     │ OData
┌────▼────────┐     ┌──────────────┐
│ 700+ 1C     │ ←───│cluster-service│ gRPC
│ Bases       │     │ (8088)       │ ↓
└─────────────┘     └──────────────┘ ras-grpc-gw
```

**Поток данных:**
```
User → Frontend → API Gateway → Orchestrator → Celery → Redis Queue
→ Go Worker → OData → 1C Base → Results → WebSocket → User
```

---

## 📁 Структура monorepo

```
command-center-1c/
├── go-services/              # Go микросервисы
│   ├── api-gateway/          # HTTP router, auth, rate limit
│   ├── worker/               # Parallel processing (x2 replicas)
│   ├── batch-service/        # Batch operations (в разработке)
│   ├── cluster-service/      # 1C cluster management (RAS/gRPC) ← NEW
│   └── shared/               # Общий код (auth, logger, metrics, models)
├── orchestrator/             # Python/Django
│   ├── apps/
│   │   ├── databases/        # Database CRUD, OData, health checks
│   │   ├── operations/       # Operation management
│   │   └── templates/        # Template engine
│   └── config/               # Django settings
├── frontend/                 # React + TypeScript
│   └── src/
│       ├── api/              # API client
│       ├── components/       # UI components
│       ├── pages/            # App pages
│       └── stores/           # State management (Zustand)
├── infrastructure/
│   ├── docker/               # Dockerfiles
│   ├── k8s/                  # Kubernetes manifests
│   ├── monitoring/           # Prometheus + Grafana configs
│   └── terraform/            # IaC (planned)
├── docs/                     # Документация
└── docker-compose.yml        # Dev environment (11 services)
```

---

## 🔗 Ключевые зависимости

**Runtime dependencies:**
```
ras-grpc-gw:9999 (gRPC) ← cluster-service:8088
postgres:5432, redis:6379 ← orchestrator:8000, celery-worker, celery-beat
orchestrator:8000 ← api-gateway:8080
redis:6379 ← worker (x2 replicas)
api-gateway:8080 ← frontend:3000
```

**Важно:**
- API Gateway НЕ зависит напрямую от Workers
- Workers автономны, масштабируются независимо (deploy.replicas)
- Frontend общается ТОЛЬКО с API Gateway
- cluster-service требует внешний форк ras-grpc-gw (в ../ras-grpc-gw)

---

## 🛠️ Технологический стек

| Компонент | Язык | Фреймворк | Порт |
|-----------|------|-----------|------|
| **API Gateway** | Go 1.21+ | Gin | 8080 |
| **Workers** | Go 1.21+ | stdlib + goroutines | - |
| **cluster-service** | Go 1.21+ | gRPC client | 8088 |
| **Orchestrator** | Python 3.11+ | Django 4.2+ DRF | 8000 |
| **Task Queue** | Python 3.11+ | Celery 5.3+ | - |
| **Frontend** | TypeScript | React 18.2 + Ant Design | 3000 |

**Data:**
- PostgreSQL 15 (5432) - primary DB
- Redis 7 (6379) - queue + cache
- ClickHouse (8123, 9000) - analytics (в dev окружении)

**Monitoring:**
- Prometheus (9090), Grafana (3001)

**External:**
- ras-grpc-gw (9999 gRPC, 8081 HTTP) - форк для 1C RAS

---

## ⚠️ Критические ограничения

1. **Транзакции 1С < 15 секунд** - разбивай длинные операции на короткие транзакции
2. **Connection limits** - max 3-5 concurrent connections per база 1С
3. **Worker pool size** - Phase 1: 10-20, Phase 2: 20-50, Production: auto-scale по queue depth
4. **OData batch** - используй $batch для групповых операций (100-500 records/batch)
5. **Rate limiting** - 100 req/min per user (default), отдельные лимиты для массовых операций

---

## 🚀 Quick Start

**Первый раз:**
```bash
git clone <repo>
cd command-center-1c
cp .env.example .env
make setup          # Install dependencies
make dev            # Start all services (11 containers)
```

**Ежедневная разработка:**
```bash
make dev            # Start all
make logs           # View logs
make test           # Run tests
make stop           # Stop all
```

**Доступ к сервисам:**
- Frontend: http://localhost:3000
- API Gateway: http://localhost:8080
- Orchestrator: http://localhost:8000
- API Docs: http://localhost:8000/api/docs
- cluster-service: http://localhost:8088/health
- ras-grpc-gw: http://localhost:8081/health (gRPC: 9999)
- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090

---

## 🔧 Локальная разработка

**Hybrid подход:** Infrastructure в Docker, Application сервисы на хосте

**Быстрый старт:**
```bash
# 1. Создать .env для локальной разработки
cp .env.local.example .env.local

# 2. Запустить все сервисы локально
./scripts/dev/start-all.sh

# 3. Проверить статус
./scripts/dev/health-check.sh
```

**Управление сервисами:**
```bash
./scripts/dev/start-all.sh        # Запустить всё
./scripts/dev/stop-all.sh         # Остановить всё
./scripts/dev/restart.sh <service> # Перезапустить сервис
./scripts/dev/logs.sh <service>    # Просмотр логов
./scripts/dev/health-check.sh     # Проверка здоровья
```

**Доступные сервисы:**
- orchestrator, celery-worker, celery-beat
- api-gateway, worker, ras-grpc-gw, cluster-service
- frontend

**Документация:**
- **[LOCAL_DEVELOPMENT_GUIDE.md](docs/LOCAL_DEVELOPMENT_GUIDE.md)** - Полное руководство (23KB)
- **[LOCAL_DEV_MIGRATION_SUMMARY.md](LOCAL_DEV_MIGRATION_SUMMARY.md)** - Сводка миграции
- **Skill:** `cc1c-devops` - DevOps операции для локальной разработки

---

## 🔗 Ключевые документы

**⭐ Обязательно к прочтению:**
- **[ROADMAP.md](docs/ROADMAP.md)** - Balanced план (Phases 1-5, 14-16 недель)
- **[START_HERE.md](docs/START_HERE.md)** - Быстрый старт (2 мин)
- **[EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md)** - Краткое резюме

**Практические гайды:**
- **[1C_ADMINISTRATION_GUIDE.md](docs/1C_ADMINISTRATION_GUIDE.md)** - RAS/RAC, gRPC, endpoint management
- **[DJANGO_CLUSTER_INTEGRATION.md](docs/DJANGO_CLUSTER_INTEGRATION.md)** - cluster-service ↔ Django
- **[ODATA_INTEGRATION.md](docs/ODATA_INTEGRATION.md)** - Batch операции

**Техническая документация:**
- [Architecture](docs/architecture/) - Архитектурные решения
- [API](docs/api/) - REST API спецификация
- [Deployment](docs/deployment/) - Развертывание
- [README.md](README.md) - Main project README

**История:**
- [Sprint Progress](docs/archive/sprints/) - Детальная история спринтов
- [Roadmap Variants](docs/archive/roadmap_variants/) - MVP/Enterprise варианты (архив)

---

## 💡 Tips для AI агентов

1. **Работаем ТОЛЬКО по Balanced roadmap** - MVP/Enterprise в docs для справки
2. **Локальная разработка** - используй `./scripts/dev/start-all.sh` для запуска, skill `cc1c-devops` для DevOps
3. **Следуй monorepo структуре** - не создавай файлы в неправильных местах
4. **Go shared code** - auth/logger/config в go-services/shared/
5. **Django apps независимы** - минимум cross-app imports
6. **Frontend → API Gateway ТОЛЬКО** - никаких прямых вызовов Orchestrator
7. **ras-grpc-gw** - наш форк в C:/1CProject/ras-grpc-gw, запускается локально (не Docker)
8. **cluster-service** - зависит от ras-grpc-gw, запускай ras-grpc-gw первым
9. **Транзакции 1С < 15 сек** - критично!
10. **Тесты обязательны** - coverage > 70%
11. **При сомнениях** - читай docs/ROADMAP.md (Balanced) или docs/LOCAL_DEVELOPMENT_GUIDE.md

---

**Версия:** 2.1
**Последнее обновление:** 2025-11-03
**Фаза:** Phase 1, Week 3-4 (Core Functionality)
**Sprint:** 2.1 (Task Queue & Worker) в работе
**Dev Mode:** Hybrid (Infrastructure в Docker, Application на хосте)
