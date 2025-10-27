---
description: Start all services for local development with Docker Compose
---

Запустить все сервисы для локальной разработки.

## Действия

1. **Проверить Docker и docker-compose**
   ```bash
   docker --version
   docker-compose --version
   ```

2. **Перейти в корневую директорию проекта**
   ```bash
   cd /c/1CProject/command-center-1c
   ```

3. **Создать .env файл если его нет**
   ```bash
   cp .env.example .env 2>/dev/null || echo "Используем существующий .env"
   ```

4. **Запустить Docker Compose**
   ```bash
   docker-compose up -d
   ```

5. **Проверить статус сервисов**
   ```bash
   docker-compose ps
   ```

6. **Просмотреть логи (опционально)**
   ```bash
   docker-compose logs -f
   ```

## Проверка после запуска

- **API Gateway:** http://localhost:8080/health
- **Orchestrator:** http://localhost:8000/health (или /admin)
- **Frontend:** http://localhost:3000
- **Redis:** localhost:6379
- **PostgreSQL:** localhost:5432

## Параметры (если есть)

Нет параметров - команда запускает все сервисы со значениями из docker-compose.yml

## Примеры

```bash
# Простой старт
make dev-start

# Или напрямую
cd /c/1CProject/command-center-1c && docker-compose up -d

# Проверить что все работает
docker-compose ps
docker-compose logs orchestrator  # смотреть логи конкретного сервиса
```

## Troubleshooting

**Порт уже занят:**
```bash
# Убить процесс
lsof -i :8080  # Find process on port 8080
kill -9 <PID>  # Kill the process

# Или изменить порт в docker-compose.yml
```

**Проблема с базой данных:**
```bash
# Проверить статус PostgreSQL
docker-compose logs postgres

# Пересоздать контейнер
docker-compose down
docker-compose up -d
```

**Очистить все и начать заново:**
```bash
docker-compose down -v        # -v удаляет volumes
docker system prune -a        # удалить все неиспользуемые образы
docker-compose up -d          # запустить заново
```

## Связанные Commands

- `test-all` - запустить все тесты
- `docker-logs` - просмотреть логи
- `dev-stop` - остановить сервисы
