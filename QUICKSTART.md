# Quick Start Guide

Быстрый старт для разработчиков CommandCenter1C.

## Предварительные требования

- Docker & Docker Compose
- Go 1.21+
- Python 3.11+
- Node.js 20+
- Git

## Первый запуск

### 1. Клонирование и настройка

```bash
cd command-center-1c
cp .env.example .env
# Отредактируйте .env при необходимости
```

### 2. Запуск через Docker Compose (рекомендуется)

```bash
docker-compose up -d
```

Сервисы будут доступны на:
- Frontend: http://localhost:3000
- API Gateway: http://localhost:8080
- Orchestrator: http://localhost:8000
- Grafana: http://localhost:3001
- Prometheus: http://localhost:9090

### 3. Локальная разработка

#### Go Services

```bash
cd go-services

# Запуск API Gateway
cd api-gateway
go run cmd/main.go

# Запуск Worker (в другом терминале)
cd ../worker
go run cmd/main.go
```

#### Django Orchestrator

```bash
cd orchestrator

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements/development.txt

# Применить миграции
python manage.py migrate

# Запустить сервер
python manage.py runserver

# Запустить Celery worker (в другом терминале)
celery -A config worker --loglevel=info
```

#### Frontend

```bash
cd frontend

# Установить зависимости
npm install

# Запустить dev сервер
npm run dev
```

## Проверка работоспособности

### Health checks

```bash
# API Gateway
curl http://localhost:8080/health

# Orchestrator
curl http://localhost:8000/health
```

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f api-gateway
docker-compose logs -f orchestrator
docker-compose logs -f worker
```

## Остановка

```bash
# Остановить все сервисы
docker-compose down

# Остановить и удалить volumes
docker-compose down -v
```

## Следующие шаги

1. Изучите документацию в `docs/`
2. Посмотрите ROADMAP.md для понимания текущей фазы
3. Прочитайте CLAUDE.md для AI-агентов
4. Начните с задач из Phase 1, Week 1-2

## Полезные команды

```bash
# Пересобрать конкретный сервис
docker-compose build api-gateway

# Перезапустить конкретный сервис
docker-compose restart worker

# Выполнить команду в контейнере
docker-compose exec orchestrator python manage.py shell

# Посмотреть запущенные контейнеры
docker-compose ps
```

## Troubleshooting

### Ошибка подключения к БД

Убедитесь что PostgreSQL запущен и доступен:
```bash
docker-compose ps postgres
docker-compose logs postgres
```

### Ошибки при сборке Go services

Проверьте что go.work существует:
```bash
cd go-services
cat go.work
```

### Frontend не запускается

Удалите node_modules и переустановите:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Дополнительно

- Swagger API: http://localhost:8000/api/docs/
- Django Admin: http://localhost:8000/admin/
- Prometheus UI: http://localhost:9090
- Grafana (admin/admin): http://localhost:3001
