# Конфигурация портов для Worktree

**Worktree:** `feature/unified-workflow-platform`
**Проблема:** Конфликты портов с основной веткой
**Дата:** 2025-11-23

---

## ⚠️ Обнаруженные конфликты

### Основная ветка (master) - запущенные порты

```
PostgreSQL:   5432
Redis:        6379
Prometheus:   9090
Grafana:      5000
Orchestrator: 8000
API Gateway:  8080
Frontend:     5173
RAS Adapter:  8088
```

### Feature worktree - docker-compose.yml (ДО изменений)

```
PostgreSQL:   5432  ❌ КОНФЛИКТ
Redis:        6379  ❌ КОНФЛИКТ
Prometheus:   9090  ❌ КОНФЛИКТ
Grafana:      3001  ✅ OK
Orchestrator: 8000  ❌ КОНФЛИКТ
API Gateway:  8080  ❌ КОНФЛИКТ
Frontend:     5173  ❌ КОНФЛИКТ
```

---

## 🎯 Решения

### Вариант 1: Shared Infrastructure (РЕКОМЕНДОВАНО) ⭐

**Суть:** Feature worktree использует инфраструктуру из основной ветки.

**Преимущества:**
- ✅ Экономия ресурсов (RAM, CPU)
- ✅ Быстрый старт (контейнеры уже работают)
- ✅ Одна БД → видны изменения из обоих worktree
- ✅ Идеально для Week 5-11 (только backend development)

**Команды запуска:**

```bash
# 1. Убедитесь что основная ветка запущена
cd /c/1CProject/command-center-1c
docker ps  # Должны быть: postgres, redis, prometheus, grafana

# 2. Перейдите в feature worktree
cd /c/1CProject/command-center-1c-unified-workflow

# 3. Скопируйте .env.example → .env.local (используем localhost)
cp .env.example .env.local

# 4. Django Orchestrator (на порту 8100 вместо 8000)
cd orchestrator
source venv/Scripts/activate
export DB_HOST=localhost
export DB_PORT=5432  # Используем Postgres из основной ветки
export REDIS_HOST=localhost
export REDIS_PORT=6379  # Используем Redis из основной ветки

# Применить миграции (к той же БД!)
python manage.py migrate

# Запустить на ДРУГОМ порту
python manage.py runserver 8100

# 5. В другом терминале - Celery Worker
cd /c/1CProject/command-center-1c-unified-workflow/orchestrator
source venv/Scripts/activate
celery -A config worker --loglevel=info

# 6. Frontend (если нужен, на порту 5174)
cd /c/1CProject/command-center-1c-unified-workflow/frontend
npm install
VITE_API_URL=http://localhost:8100 npm run dev -- --port 5174
```

**Доступные endpoints:**

```
Shared (from main worktree):
- PostgreSQL:   localhost:5432
- Redis:        localhost:6379
- Prometheus:   localhost:9090
- Grafana:      localhost:5000

Feature worktree (isolated):
- Orchestrator: localhost:8100
- Frontend:     localhost:5174
```

---

### Вариант 2: Isolated Infrastructure (Полная изоляция)

**Суть:** Feature worktree имеет собственную инфраструктуру (порты +100).

**Преимущества:**
- ✅ Полная изоляция
- ✅ Разные БД → нет риска конфликтов данных
- ✅ Можно тестировать миграции безопасно

**Недостатки:**
- ❌ Двойное потребление ресурсов
- ❌ Дольше стартует

**Команды запуска:**

```bash
cd /c/1CProject/command-center-1c-unified-workflow

# 1. Запустить изолированную инфраструктуру
docker-compose -f docker-compose.workflow.yml up -d

# Проверить
docker ps  # Должны быть: postgres-workflow, redis-workflow, etc

# 2. Использовать .env.workflow
cp .env.workflow .env.local

# 3. Django Orchestrator (на порту 8100)
cd orchestrator
source venv/Scripts/activate
python manage.py migrate
python manage.py runserver 8100

# 4. Celery Worker
cd /c/1CProject/command-center-1c-unified-workflow/orchestrator
source venv/Scripts/activate
celery -A config worker --loglevel=info

# 5. Frontend (на порту 5274)
cd /c/1CProject/command-center-1c-unified-workflow/frontend
npm install
VITE_API_URL=http://localhost:8180 npm run dev -- --port 5274
```

**Доступные endpoints (все изолированные):**

```
PostgreSQL:   localhost:5532  (+100)
Redis:        localhost:6479  (+100)
Prometheus:   localhost:9190  (+100)
Grafana:      localhost:3101  (+100)
Orchestrator: localhost:8100  (+100)
API Gateway:  localhost:8180  (+100)
Frontend:     localhost:5274  (+100)
```

---

## 📊 Сравнение вариантов

| Критерий | Вариант 1 (Shared) | Вариант 2 (Isolated) |
|----------|-------------------|---------------------|
| **Память** | ~500MB | ~1GB |
| **Время старта** | <10 секунд | ~30 секунд |
| **Изоляция данных** | ❌ Общая БД | ✅ Раздельные БД |
| **Простота** | ✅ Проще | ⚠️ Сложнее |
| **Для Week 5-11** | ✅ Идеально | ⚠️ Избыточно |
| **Для Week 12-18** | ⚠️ Может конфликтовать | ✅ Безопасно |

---

## 🚀 Рекомендации

### Week 5-11 (Backend only)
**Используй Вариант 1 (Shared Infrastructure)**

Причины:
- Нужен только Django + Celery
- Тестируешь только models/validators/handlers
- Экономия ресурсов
- Быстрый feedback loop

### Week 12-18 (Frontend + Real-Time)
**Переключись на Вариант 2 (Isolated Infrastructure)**

Причины:
- Появляется WebSocket (порты могут конфликтовать)
- Нужна Jaeger (еще +3 порта)
- Тестируешь полную интеграцию
- Безопаснее изолировать

---

## 🔧 Переключение между вариантами

### From Shared → Isolated

```bash
# 1. Остановить процессы feature worktree
# Ctrl+C в терминалах Django/Celery/Frontend

# 2. Запустить изолированную инфраструктуру
cd /c/1CProject/command-center-1c-unified-workflow
docker-compose -f docker-compose.workflow.yml up -d

# 3. Применить миграции к новой БД
cd orchestrator
source venv/Scripts/activate
export DB_PORT=5532  # Isolated PostgreSQL
python manage.py migrate

# 4. Перезапустить сервисы с новыми портами
# (см. команды в Вариант 2)
```

### From Isolated → Shared

```bash
# 1. Остановить изолированную инфраструктуру
cd /c/1CProject/command-center-1c-unified-workflow
docker-compose -f docker-compose.workflow.yml down

# 2. Использовать shared БД
cd orchestrator
source venv/Scripts/activate
export DB_PORT=5432  # Shared PostgreSQL
python manage.py migrate

# 3. Запустить на порту 8100
python manage.py runserver 8100
```

---

## ✅ Validation Checklist

**После запуска (Вариант 1 - Shared):**

```bash
# 1. Проверить БД доступна
psql -h localhost -p 5432 -U commandcenter -d commandcenter
# Должно подключиться

# 2. Проверить Redis доступен
redis-cli -h localhost -p 6379 ping
# Должно вернуть: PONG

# 3. Проверить Django работает
curl http://localhost:8100/admin/
# Должно вернуть HTML

# 4. Проверить что основная ветка НЕ конфликтует
cd /c/1CProject/command-center-1c
curl http://localhost:8000/admin/
# Основная ветка тоже работает
```

**После запуска (Вариант 2 - Isolated):**

```bash
# 1. Проверить изолированную БД
docker exec commandcenter-postgres-workflow pg_isready
# Должно: accepting connections

# 2. Проверить изолированный Redis
docker exec commandcenter-redis-workflow redis-cli ping
# Должно: PONG

# 3. Проверить Django
curl http://localhost:8100/admin/
# HTML ответ

# 4. Проверить что ОБА worktree работают одновременно
curl http://localhost:8000/admin/  # Main worktree
curl http://localhost:8100/admin/  # Feature worktree
# Оба должны отвечать
```

---

## 📝 Troubleshooting

### Problem: "Port 5432 already in use"

**Solution (Вариант 1):**
```bash
# Убедись что используешь localhost:5432 (shared)
export DB_PORT=5432
```

**Solution (Вариант 2):**
```bash
# Убедись что isolated Postgres запущен на 5532
docker ps | grep postgres-workflow
export DB_PORT=5532
```

### Problem: "Connection refused to PostgreSQL"

**Check:**
```bash
# Вариант 1: Проверь что контейнер из main worktree работает
docker ps | grep postgres

# Вариант 2: Проверь что isolated контейнер работает
docker ps | grep postgres-workflow
```

### Problem: "Django migrations conflict"

**Cause:** Shared БД, оба worktree применяют миграции

**Solution:**
- Вариант 1: Нормально! Оба worktree видят одинаковые миграции
- Вариант 2: Switch to isolated infrastructure

---

## 🎯 Recommended Setup for Week 5

**Для начала Week 5 (Models + Migrations):**

```bash
# 1. Main worktree остается запущенным (НЕ трогаем)
cd /c/1CProject/command-center-1c
# Docker контейнеры работают

# 2. Feature worktree использует shared infrastructure
cd /c/1CProject/command-center-1c-unified-workflow/orchestrator
source venv/Scripts/activate

# 3. Создать models.py
# (см. Week 5 roadmap)

# 4. Создать миграции
python manage.py makemigrations templates

# 5. Применить к shared БД
python manage.py migrate

# 6. Запустить Django на порту 8100
python manage.py runserver 8100

# 7. Писать тесты
pytest apps/templates/workflow/tests/ -v
```

**Result:** Быстрая разработка без конфликтов портов! ✅

---

**Status:** ✅ READY
**Recommendation:** Start with Vариант 1 (Shared), switch to Вариант 2 at Week 12
