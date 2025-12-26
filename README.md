# 🎯 CommandCenter1C

> Централизованная платформа управления данными для 700+ баз 1С:Бухгалтерия 3.0

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Go Version](https://img.shields.io/badge/go-1.21+-blue.svg)](https://golang.org)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![React Version](https://img.shields.io/badge/react-18.2+-blue.svg)](https://reactjs.org)

---

## 📋 О проекте

**CommandCenter1C** - универсальная микросервисная платформа для централизованного управления и массовых операций с данными в сотнях баз 1С:Бухгалтерия предприятия 3.0.

### Ключевые возможности

- ✅ **Массовые операции** - создание пользователей, изменение документов, распределение товаров
- ✅ **Параллельная обработка** - до 500 баз одновременно
- ✅ **Real-time мониторинг** - отслеживание выполнения операций в реальном времени
- ✅ **Система шаблонов** - настраиваемые операции для любых задач
- ✅ **Enterprise-grade** - Prometheus, Grafana, RBAC, audit logging

### Экономия

- **10-100x** ускорение массовых операций
- **97%** экономия времени
- **ROI 260-1200%** в первый год

---

## 🏗️ Архитектура

```
┌─────────┐
│ React   │ TypeScript + Ant Design
│ (5173)  │
└────┬────┘
     │ HTTP + WebSocket
┌────▼────┐
│ Go API  │ Gin + JWT + Rate Limiting
│ Gateway │
│ (8180)  │
└────┬────┘
     │ HTTP
┌────▼────────┐
│ Django      │ DRF
│ Orchestr.   │ Business Logic
│ (8200)      │
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
     │ OData + RAS (direct)
┌────▼────────┐
│ 700+ 1C     │
│ Bases       │
└─────────────┘
     │
     ▼
   RAS (1545)
```

---

## 🚀 Quick Start

### Требования

- **Docker** >= 20.10
- **Docker Compose** >= 2.0
- **Go** >= 1.21 (для разработки)
- **Python** >= 3.11 (для разработки)
- **Node.js** >= 20 (для разработки)

### Запуск локально (Hybrid режим разработки)

```bash
# Клонировать репозиторий
git clone https://github.com/your-org/command-center-1c.git
cd command-center-1c

# Настроить окружение
cp .env.example .env.local
# Отредактировать .env.local (DB_HOST=localhost, REDIS_HOST=localhost)

# Установить зависимости
cd orchestrator && python -m venv venv && source venv/Scripts/activate && pip install -r requirements.txt && cd ..
cd frontend && npm install && npx playwright install && cd ..

# Запустить все сервисы (с умной автопересборкой)
./scripts/dev/start-all.sh

# Проверить статус
./scripts/dev/health-check.sh
```

**Опции запуска:**
```bash
./scripts/dev/start-all.sh                    # Умная пересборка измененных
./scripts/dev/start-all.sh --force-rebuild    # Принудительная пересборка всех Go
./scripts/dev/start-all.sh --no-rebuild       # Быстрый старт без пересборки
./scripts/dev/start-all.sh --parallel-build   # Параллельная сборка
```

Сервисы будут доступны на:
- **Frontend**: http://localhost:5173
- **API Gateway**: http://localhost:8180/health
- **Orchestrator**:
  - Admin Panel: http://localhost:8200/admin
  - API Docs (Swagger): http://localhost:8200/api/docs

---

## 📁 Структура проекта

```
command-center-1c/
├── .github/              # GitHub Actions CI/CD
│   └── workflows/
├── go-services/          # Go микросервисы
│   ├── api-gateway/      # API Gateway (Go + Gin)
│   ├── worker/           # Go Workers для параллельной обработки
│   └── shared/           # Общий Go код
├── orchestrator/         # Python/Django Orchestrator
│   ├── config/           # Django настройки
│   └── apps/             # Django приложения
├── frontend/             # React фронтенд
│   └── src/              # Исходники React
├── infrastructure/       # DevOps конфигурация
│   ├── docker/           # Dockerfiles
│   ├── k8s/              # Kubernetes manifests
│   └── terraform/        # Terraform для инфраструктуры
├── docs/                 # Документация
│   ├── architecture/     # Архитектурные решения
│   ├── api/              # API спецификация
│   └── deployment/       # Инструкции по развертыванию
├── scripts/              # Утилиты и скрипты
├── docker-compose.yml    # Docker Compose для разработки
└── Makefile              # Команды для управления проектом
```

---

## 🛠️ Технологический стек

### Backend

| Компонент | Технология | Назначение |
|-----------|-----------|------------|
| **API Gateway** | Go + Gin | Маршрутизация, аутентификация |
| **Orchestrator** | Python + Django + DRF | Бизнес-логика, API |
| **Task Queue** | Redis Streams | Очереди задач |
| **Workers** | Go + Goroutines | Массовая обработка 1С |
| **OData (direct)** | Go Worker | Интеграция с 1С |

### Frontend

- **React** + TypeScript
- **Ant Design Pro** - UI компоненты
- **WebSocket** - Real-time updates
- **Axios** - HTTP client

### Data & Infrastructure

- **PostgreSQL** - Primary database
- **Redis** - Queue + Cache
- **ClickHouse** - Analytics
- **Prometheus** + **Grafana** - Monitoring
- **Docker** + **Kubernetes** - Deployment

---

## 📊 Roadmap

> **⭐ Проект реализуется по варианту: Balanced Approach (14-16 недель)**
> Детальный план см. в [docs/ROADMAP.md](docs/ROADMAP.md)

### Phase 1: MVP Foundation (Week 1-6) ✅ Week 1-2 Complete
- [x] Базовая инфраструктура (Sprint 1.1-1.3)
- [x] Direct RAS integration in Worker (Phase 2)
- [ ] Core functionality (Week 3-4)
- [ ] API & Basic UI (Week 5-6)
- [ ] Testing & Deployment (Week 5-6)

### Phase 2: Extended Functionality (Week 7-10)
- [ ] Система шаблонов (4+ операций)
- [ ] Worker scaling
- [ ] Advanced UI с WebSocket
- [ ] До 500 баз параллельно

### Phase 3: Monitoring & Observability (Week 11-12)
- [ ] Prometheus + Grafana
- [ ] ClickHouse аналитика
- [ ] Alerting

### Phase 4: Advanced Features (Week 13-15)
- [ ] RBAC security
- [ ] Backup/recovery
- [ ] External integrations

### Phase 5: Production Hardening (Week 16)
- [ ] Load testing
- [ ] Kubernetes deployment
- [ ] Documentation & training

Подробный roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

---

## 🔧 Команды для разработки

```bash
# Запуск в dev режиме
make dev

# Запуск тестов
make test

# Сборка всех Docker образов
make build

# Деплой на staging
make deploy-staging

# Деплой на production
make deploy-prod

# Просмотр логов
make logs

# Остановка всех сервисов
make stop

# Очистка
make clean
```

---

## 📖 Документация

### Roadmap и Планирование
- **[START HERE](docs/START_HERE.md)** - Быстрый старт по документации roadmap (2 мин)
- **[Executive Summary](docs/EXECUTIVE_SUMMARY.md)** - Для принятия решений (5-10 мин)
- **[Roadmap](docs/ROADMAP.md)** - Детальный план разработки (60-90 мин)
- **[Index](docs/INDEX.md)** - Полная навигация по документации (10 мин)

### Практические гайды ← NEW
- **[1C Administration Guide](docs/1C_ADMINISTRATION_GUIDE.md)** - RAS/RAC, gRPC, endpoint management
- **[OData Integration](docs/ODATA_INTEGRATION.md)** - Batch операции для массовой обработки данных

### Техническая документация
- [Architecture Overview](docs/architecture/README.md)
- [API Documentation](docs/api/README.md)
- [Deployment Guide](docs/deployment/README.md)
- [Development Guide](docs/development/README.md)
- [CLAUDE.md](CLAUDE.md) - Инструкции для AI агентов
- [Contributing](CONTRIBUTING.md)

---

## 🤝 Contributing

Мы приветствуем вклад в проект! Пожалуйста, ознакомьтесь с [CONTRIBUTING.md](CONTRIBUTING.md) для деталей.

### Development Workflow

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit изменения (`git commit -m 'Add some AmazingFeature'`)
4. Push в branch (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

---

## 📝 Лицензия

Distributed under the MIT License. See `LICENSE` for more information.

---

## 📧 Контакты

- **Project Lead**: [Ваше имя]
- **Email**: [email@example.com]
- **Telegram**: [@your_handle]
- **Issues**: [GitHub Issues](https://github.com/your-org/command-center-1c/issues)

---

## ⭐ Acknowledgments

- [1С:Предприятие 8](https://v8.1c.ru/) - Платформа 1С
- [Go](https://golang.org/) - Backend сервисы
- [Django](https://www.djangoproject.com/) - Orchestrator
- [React](https://reactjs.org/) - Frontend
- [Ant Design](https://ant.design/) - UI компоненты

---

**Made with ❤️ for 1C community**
