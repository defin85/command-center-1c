# Troubleshooting Reference

Детальные решения типичных проблем при разработке CommandCenter1C.

## Problem 1: Services Won't Start

**Symptom:**
```
Error: listen tcp :8080: bind: address already in use
```

**Diagnosis:**
```bash
# Windows (GitBash)
netstat -ano | findstr :8080
tasklist /FI "PID eq <pid>"

# Linux/Mac
lsof -i :8080
ps aux | grep <pid>
```

**Solution:**
```bash
# Kill specific process
taskkill /PID <pid> /F  # Windows
kill -9 <pid>  # Linux/Mac

# Or stop all and restart
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh
```

**Prevention:**
- Всегда используй `./scripts/dev/stop-all.sh` перед выключением
- Проверяй PID файлы перед запуском

---

## Problem 2: Database Connection Errors

**Symptom:**
```
django.db.utils.OperationalError: could not connect to server
FATAL: password authentication failed for user "commandcenter"
```

**Diagnosis:**
```bash
# Check if PostgreSQL is running
docker-compose -f docker-compose.local.yml ps postgres

# Check logs
docker-compose -f docker-compose.local.yml logs postgres

# Test connection
docker-compose -f docker-compose.local.yml exec postgres pg_isready
```

**Solution:**
```bash
# Restart database
docker-compose -f docker-compose.local.yml restart postgres

# Wait for ready
docker-compose -f docker-compose.local.yml exec postgres pg_isready

# Check .env.local
cat .env.local | grep DB_HOST
# Should be: DB_HOST=localhost (NOT postgres)

# Test manual connection
docker exec -it postgres psql -U commandcenter -d commandcenter -c "SELECT 1;"
```

**Common Causes:**
- DB_HOST=postgres в .env.local (должно быть localhost)
- PostgreSQL контейнер не запущен
- Неправильный пароль в .env.local

---

## Problem 3: Redis Connection Issues

**Symptom:**
```
redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379
Connection refused
```

**Diagnosis:**
```bash
# Check Redis status
docker-compose -f docker-compose.local.yml ps redis

# Test connection
docker-compose -f docker-compose.local.yml exec redis redis-cli ping
# Should return: PONG
```

**Solution:**
```bash
# Restart Redis
docker-compose -f docker-compose.local.yml restart redis

# Check .env.local
cat .env.local | grep REDIS_HOST
# Should be: REDIS_HOST=localhost (NOT redis)

# Verify port
netstat -ano | findstr :6379  # Windows
lsof -i :6379  # Linux/Mac
```

**Common Causes:**
- REDIS_HOST=redis в .env.local (должно быть localhost)
- Redis контейнер не запущен
- Неправильный порт в .env.local

---

## Problem 4: Process Not Starting

**Symptom:**
```
✗ Не удалось запустить Django Orchestrator
Process exited immediately
```

**Diagnosis:**
```bash
# Check logs
cat logs/orchestrator.log

# Run manually for debugging
cd orchestrator
source venv/Scripts/activate
python manage.py runserver 0.0.0.0:8000
```

**Solution:**
```bash
# Check dependencies
cd orchestrator
source venv/Scripts/activate
pip install -r requirements.txt

# Check database connection
python manage.py check --database default

# Check migrations
python manage.py showmigrations

# Run migrations if needed
python manage.py migrate

# Check Python version
python --version
# Should be: Python 3.11+
```

**Common Causes:**
- Missing dependencies (не установлены packages)
- Database не готова (ждет миграции)
- Неправильная версия Python
- Неправильные переменные окружения в .env.local

---

## Problem 5: Frontend Not Loading

**Symptom:**
```
Module not found: Can't resolve 'react'
Failed to compile
```

**Diagnosis:**
```bash
cd frontend

# Check logs
cat ../logs/frontend.log

# Check node_modules
ls -la node_modules/react
```

**Solution:**
```bash
cd frontend

# Install dependencies
npm install

# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install

# Run manually for debugging
npm run dev

# Check Node.js version
node --version
# Should be: v18+

# Check npm version
npm --version
```

**Common Causes:**
- node_modules не установлены
- Устаревшая версия Node.js
- Поврежденный package-lock.json
- Неправильные переменные окружения в .env.local

---

## Problem 6: PID Files Lost/Corrupted

**Symptom:**
```
⚠️  orchestrator: PID файл не найден
Cannot find process with PID
```

**Diagnosis:**
```bash
# Check PID files
ls -la pids/

# Check if processes are running
netstat -ano | findstr :8080  # Windows
lsof -i :8080  # Linux/Mac
```

**Solution:**
```bash
# Clean up and restart
rm -rf pids/*.pid

# Kill any remaining processes by port
# Find PID
netstat -ano | findstr :8080  # Windows
lsof -i :8080  # Linux/Mac

# Kill it
taskkill /PID <pid> /F  # Windows
kill -9 <pid>  # Linux/Mac

# Start fresh
./scripts/dev/start-all.sh
```

**Prevention:**
- Не удаляй pids/ директорию вручную
- Всегда используй ./scripts/dev/stop-all.sh для остановки

---

## Problem 7: Celery Tasks Not Processing

**Symptom:**
- Operations stuck in "pending"
- No worker activity in logs
- Tasks accumulate in Redis queue

**Diagnosis:**
```bash
# Check Celery Worker logs
./scripts/dev/logs.sh celery-worker

# Check Redis queue
docker-compose -f docker-compose.local.yml exec redis redis-cli
> LLEN operations_queue
> LRANGE operations_queue 0 -1

# Check Celery worker status
cd orchestrator
source venv/Scripts/activate
celery -A config inspect active
celery -A config inspect stats
```

**Solution:**
```bash
# Restart Celery Worker
./scripts/dev/restart.sh celery-worker

# Check worker is connected
./scripts/dev/logs.sh celery-worker | grep "ready"

# Flush Redis queue (если tasks поврежденные)
docker-compose -f docker-compose.local.yml exec redis redis-cli FLUSHALL

# Check Celery configuration
cd orchestrator
cat config/celery.py
```

**Common Causes:**
- Celery worker не запущен или упал
- Redis недоступен
- Неправильная конфигурация CELERY_BROKER_URL
- Задачи с ошибками блокируют очередь

---

## Problem 8: cluster-service Connection Refused (port 9999)

**Symptom:**
```
Error: connection refused on port 9999
cluster-service cannot connect to ras-grpc-gw
gRPC dial error
```

**Diagnosis:**
```bash
# Check if ras-grpc-gw is running
netstat -ano | findstr :9999  # Windows
lsof -i :9999  # Linux/Mac

# Check ras-grpc-gw process
ps aux | grep ras-grpc-gw  # Linux/Mac
tasklist | findstr ras-grpc-gw.exe  # Windows

# Check health endpoint
curl http://localhost:8081/health
# Expected: {"service":"ras-grpc-gw","status":"healthy",...}
```

**Solution:**
```bash
# Start ras-grpc-gw FIRST
cd ../ras-grpc-gw
go run cmd/main.go localhost:1545

# Wait 3-5 seconds for initialization

# Then start cluster-service
cd /c/1CProject/command-center-1c/go-services/cluster-service
go run cmd/main.go

# Check cluster-service logs
cd /c/1CProject/command-center-1c
./scripts/dev/logs.sh cluster-service
```

**⚠️ КРИТИЧНО:** ras-grpc-gw должен быть запущен ПЕРЕД cluster-service!

**Common Causes:**
- ras-grpc-gw не запущен
- Неправильный порядок запуска (cluster-service перед ras-grpc-gw)
- ras-grpc-gw упал или не готов
- Неправильный GRPC_GATEWAY_ADDR в переменных окружения

---

## Problem 9: batch-service "1cv8.exe not found"

**Symptom:**
```
Error: exec: "1cv8.exe": executable file not found
Cannot find 1cv8.exe in PATH
```

**Diagnosis:**
```bash
# Check environment variable
echo $EXE_1CV8_PATH  # Linux/Mac/GitBash
set EXE_1CV8_PATH  # Windows CMD

# Check if file exists
ls "$EXE_1CV8_PATH"  # Linux/Mac/GitBash
dir "%EXE_1CV8_PATH%"  # Windows CMD

# Check batch-service logs
./scripts/dev/logs.sh batch-service
```

**Solution:**
```bash
# Set correct path in .env.local
cat >> .env.local << EOF
EXE_1CV8_PATH=C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe
V8_DEFAULT_TIMEOUT=300
EOF

# Export in current session (GitBash)
export EXE_1CV8_PATH="C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe"

# Restart batch-service
cd go-services/batch-service
go run cmd/main.go

# Verify
curl http://localhost:8087/health
```

**Common Causes:**
- EXE_1CV8_PATH не установлена
- Неправильный путь к 1cv8.exe
- 1С не установлена на машине
- Неправильные права доступа к 1cv8.exe

---

## Problem 10: ras-grpc-gw "RAS server not available" (port 1545)

**Symptom:**
```
Error: cannot connect to RAS server on port 1545
RAS server not available
dial tcp: connection refused
```

**Diagnosis:**
```bash
# Test telnet connection
telnet localhost 1545

# Or use netcat
nc -zv localhost 1545  # Linux/Mac

# Check ras-grpc-gw logs
cd ../ras-grpc-gw
cat ras-grpc-gw.log | tail -50
```

**Solution:**

**Option 1: Start RAS server (if not running)**
- Открыть консоль администрирования 1С
- Подключиться к серверу кластера
- Проверить что RAS работает на порту 1545

**Option 2: Change RAS port**
```bash
# If RAS is on different port (e.g., 1546)
cd ../ras-grpc-gw
go run cmd/main.go localhost:1546

# Update environment for cluster-service
export RAS_SERVER=localhost:1546
```

**Option 3: Remote RAS server**
```bash
# Connect to remote RAS server
cd ../ras-grpc-gw
go run cmd/main.go 192.168.1.100:1545
```

**Common Causes:**
- RAS сервер 1С не запущен
- Неправильный порт RAS (не 1545)
- RAS на другой машине (нужен IP)
- Firewall блокирует порт 1545

**См. также:**
- [1C_ADMINISTRATION_GUIDE.md](../../docs/1C_ADMINISTRATION_GUIDE.md) для детальной настройки RAS

---

## Problem 11: Django Migrations Fail

**Symptom:**
```
django.db.migrations.exceptions.InconsistentMigrationHistory
Migration X is applied before its dependency Y
```

**Solution:**
```bash
cd orchestrator
source venv/Scripts/activate

# Show migration status
python manage.py showmigrations

# Rollback to specific migration
python manage.py migrate <app_name> <migration_name>

# Fake migration (mark as applied without running)
python manage.py migrate --fake <app_name> <migration_name>

# Nuclear option: reset all migrations (⚠️ removes data)
python manage.py migrate --fake <app_name> zero
python manage.py migrate <app_name>
```

---

## Problem 12: Frontend API Connection Issues

**Symptom:**
```
Failed to fetch
Network Error
CORS error
```

**Diagnosis:**
```bash
# Check API Gateway is running
curl http://localhost:8080/health

# Check Frontend config
cat frontend/.env.local | grep VITE_API_URL
# Should be: VITE_API_URL=http://localhost:8080/api/v1
```

**Solution:**
```bash
# Restart API Gateway
./scripts/dev/restart.sh api-gateway

# Check Frontend is connecting to correct URL
cd frontend
cat .env.local

# Should have:
# VITE_API_URL=http://localhost:8080/api/v1
# VITE_WS_URL=ws://localhost:8080/ws

# Restart Frontend
cd ..
./scripts/dev/restart.sh frontend
```

**⚠️ ВАЖНО:** Frontend общается ТОЛЬКО с API Gateway (`:8080`), НЕ напрямую с Orchestrator (`:8000`)!

---

## Problem 13: Go Service Build Errors

**Symptom:**
```
go: module not found
cannot find package
undefined: SomeStruct
```

**Solution:**
```bash
cd go-services/<service-name>

# Update dependencies
go mod tidy
go mod download

# Clear cache
go clean -cache -modcache

# Rebuild
go build -o ../../bin/cc1c-<service-name>.exe cmd/main.go

# Verify
./../../bin/cc1c-<service-name>.exe --version
```

---

## Complete Reset (Nuclear Option)

Когда ничего не помогает - полный сброс:

```bash
# Stop everything
./scripts/dev/stop-all.sh

# Remove Docker volumes (⚠️ removes all data)
docker-compose -f docker-compose.local.yml down -v

# Clear logs and PIDs
rm -rf logs/*.log pids/*.pid

# Clear Go caches
go clean -cache -modcache

# Clear Python caches
find orchestrator -type d -name __pycache__ -exec rm -rf {} +

# Clear Node.js
cd frontend
rm -rf node_modules package-lock.json
npm install
cd ..

# Start infrastructure
docker-compose -f docker-compose.local.yml up -d

# Wait for database
sleep 10

# Run migrations
cd orchestrator
source venv/Scripts/activate
python manage.py migrate
python manage.py createsuperuser  # if needed
cd ..

# Start all services
./scripts/dev/start-all.sh

# Check health
./scripts/dev/health-check.sh
```
