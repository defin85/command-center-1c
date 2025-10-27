---
description: Run database migrations for Django Orchestrator
---

Запустить миграции базы данных для Django Orchestrator.

## Действия

1. **Убедиться что сервисы запущены**
   ```bash
   docker-compose ps
   ```

2. **Выполнить миграции**
   ```bash
   docker-compose exec orchestrator python manage.py migrate
   ```

3. **Проверить статус миграций**
   ```bash
   docker-compose exec orchestrator python manage.py showmigrations
   ```

4. **Создать миграции (если поменялись models)**
   ```bash
   docker-compose exec orchestrator python manage.py makemigrations
   docker-compose exec orchestrator python manage.py migrate
   ```

5. **Создать суперпользователя (первый запуск)**
   ```bash
   docker-compose exec orchestrator python manage.py createsuperuser
   ```

## Параметры

Нет - команда использует значения из docker-compose.yml

## Примеры

```bash
# Запустить все миграции
docker-compose exec orchestrator python manage.py migrate

# Создать миграции из changes в models.py
docker-compose exec orchestrator python manage.py makemigrations apps.databases apps.operations

# Откатить последнюю миграцию
docker-compose exec orchestrator python manage.py migrate apps.databases 0008

# Посмотреть SQL что будет выполнен
docker-compose exec orchestrator python manage.py sqlmigrate apps.databases 0001

# Проверить что все ОК
docker-compose exec orchestrator python manage.py check
```

## Troubleshooting

**Migration fails with "table already exists":**
```bash
# Посмотреть current state
docker-compose exec orchestrator python manage.py showmigrations

# Может быть что миграция была partial
docker-compose exec orchestrator python manage.py migrate --plan
```

**"No changes detected" when running makemigrations:**
```bash
# Убедиться что model changes saved
docker-compose exec orchestrator python manage.py makemigrations --dry-run

# Force recreation
docker-compose exec orchestrator python manage.py makemigrations --noinput
```

**Database connection error:**
```bash
# Check postgres
docker-compose logs postgres

# Check connection string in .env
cat .env | grep DATABASE_URL

# Test connection directly
docker-compose exec postgres psql -U orchestrator -d command_center
```

**Circular dependency in migrations:**
```bash
# Check migration dependencies
docker-compose exec orchestrator python manage.py showmigrations --plan

# May need to merge migrations
docker-compose exec orchestrator python manage.py makemigrations --merge
```

## When to run

1. **Fresh setup** - после первого `docker-compose up`
2. **After git pull** - если есть новые миграции в коде
3. **After model changes** - если поменяли models.py
4. **Before deployment** - обязательно перед production

## Verification

```bash
# Проверить что all миграции applied
docker-compose exec orchestrator python manage.py showmigrations --list | grep "\[X\]"

# Проверить что все миграции зелёные
docker-compose exec orchestrator python manage.py migrate --plan

# Access admin panel
# http://localhost:8000/admin (если DEBUG=true)
```

## Связанные Commands

- `dev-start` - запустить сервисы (нужно перед миграциями)
- `test-all` - запустить тесты (используют test database)
- `analyze-logs` - посмотреть логи если что-то сломалось
