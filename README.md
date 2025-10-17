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
┌─────────────┐
│   Frontend  │ React + TypeScript + Ant Design
│   (Port 3000)│
└──────┬──────┘
       │
┌──────▼──────┐
│ API Gateway │ Go + Gin
│  (Port 8080)│
└──────┬──────┘
       │
┌──────▼──────────┐
│  Orchestrator   │ Python + Django + DRF
│   (Port 8000)   │
└────┬────────┬───┘
     │        │
┌────▼────┐ ┌▼─────────┐
│  Celery │ │PostgreSQL│
│  Tasks  │ │  Redis   │
└────┬────┘ └──────────┘
     │
┌────▼──────┐
│ Go Workers│ Parallel processing
│ (Scalable)│
└─────┬─────┘
      │
┌─────▼─────────┐
│ OData Adapter │
└───────┬───────┘
        │
   ┌────▼────┐
   │ 700+    │
   │ 1C Bases│
   └─────────┘
```

---

## 🚀 Quick Start

### Требования

- **Docker** >= 20.10
- **Docker Compose** >= 2.0
- **Go** >= 1.21 (для разработки)
- **Python** >= 3.11 (для разработки)
- **Node.js** >= 20 (для разработки)

### Запуск локально

```bash
# Клонировать репозиторий
git clone https://github.com/your-org/command-center-1c.git
cd command-center-1c

# Запустить все сервисы
make dev

# Или через docker-compose напрямую
docker-compose up
```

Сервисы будут доступны на:
- **Frontend**: http://localhost:3000
- **API Gateway**: http://localhost:8080
- **Orchestrator**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs

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
| **Task Queue** | Celery + Redis | Очереди задач |
| **Workers** | Go + Goroutines | Массовая обработка 1С |
| **OData Adapter** | Python/Go | Интеграция с 1С |

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

### Phase 1: MVP Foundation (Week 1-6) ✅ In Progress
- [x] Базовая инфраструктура
- [ ] Core functionality
- [ ] API & Basic UI
- [ ] Testing & Deployment

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

- [Architecture Overview](docs/architecture/README.md)
- [API Documentation](docs/api/README.md)
- [Deployment Guide](docs/deployment/README.md)
- [Development Guide](docs/development/README.md)
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
