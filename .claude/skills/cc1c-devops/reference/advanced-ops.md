# Advanced Operations Reference

Продвинутые DevOps операции для опытных разработчиков CommandCenter1C.

## Debug Specific Service

Когда нужно отладить конкретный сервис в изоляции:

```bash
# Stop all except infrastructure
./scripts/dev/stop-all.sh

# Start only infrastructure
docker-compose -f docker-compose.local.yml up -d

# Run Django migrations
cd orchestrator
source venv/Scripts/activate
python manage.py migrate

# Run service manually (foreground, with full output)
python manage.py runserver 0.0.0.0:8000

# In another terminal - run with debugger
python -m pdb manage.py runserver 0.0.0.0:8000
```

**For Go services:**
```bash
cd go-services/api-gateway

# Run with race detector
go run -race cmd/main.go

# Run with memory profiling
go run cmd/main.go -memprofile=mem.prof

# Run with CPU profiling
go run cmd/main.go -cpuprofile=cpu.prof
```

---

## Scale Workers

Запуск множества Worker instances для load testing:

```bash
# Start multiple Go Workers
for i in {1..5}; do
    cd go-services/worker
    nohup go run cmd/main.go > ../../logs/worker-$i.log 2>&1 &
    echo $! > ../../pids/worker-$i.pid
    cd ../..
done

# Monitor all workers
tail -f logs/worker-*.log

# Stop all workers
for pid_file in pids/worker-*.pid; do
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        kill -TERM "$pid" 2>/dev/null || true
        rm -f "$pid_file"
    fi
done
```

---

## Run with Specific Profiles

Docker Compose поддерживает profiles для опциональных сервисов:

```bash
# Start with ClickHouse (analytics)
docker-compose -f docker-compose.local.yml --profile analytics up -d

# Start with ras-grpc-gw
docker-compose -f docker-compose.local.yml --profile ras up -d

# Start with all profiles
docker-compose -f docker-compose.local.yml --profile analytics --profile ras up -d

# Stop specific profile
docker-compose -f docker-compose.local.yml --profile analytics down
```

---

## Hot Reload Setup (Go services)

Для автоматического перезапуска Go сервисов при изменении кода:

```bash
# Install air for Go hot reload
go install github.com/cosmtrek/air@latest

# Create .air.toml config (optional)
cd go-services/api-gateway
air init

# Run with hot reload
air

# In another service
cd ../cluster-service
air
```

**Пример .air.toml:**
```toml
[build]
  cmd = "go build -o tmp/main cmd/main.go"
  bin = "tmp/main"
  include_ext = ["go"]
  exclude_dir = ["tmp", "vendor"]
  delay = 1000
```

---

## Check Resource Usage

Мониторинг потребления ресурсов сервисами:

```bash
# Process resource usage (Windows)
for pid_file in pids/*.pid; do
    if [ -f "$pid_file" ]; then
        service=$(basename "$pid_file" .pid)
        pid=$(cat "$pid_file")
        echo "=== $service (PID: $pid) ==="
        tasklist //FI "PID eq $pid" //FO TABLE
    fi
done

# Linux/Mac
for pid_file in pids/*.pid; do
    if [ -f "$pid_file" ]; then
        service=$(basename "$pid_file" .pid)
        pid=$(cat "$pid_file")
        echo "=== $service (PID: $pid) ==="
        ps aux | grep "^.*$pid"
    fi
done

# Docker resource usage
docker stats --no-stream

# Disk usage
docker system df
du -sh logs/
du -sh pids/
```

---

## Performance Monitoring

### Monitor Live

```bash
# Watch health check every 5 seconds
watch -n 5 ./scripts/dev/health-check.sh

# Monitor specific port traffic (Windows)
netstat -ano | findstr :8080

# Monitor specific port traffic (Linux/Mac)
lsof -i :8080

# Monitor logs for errors
tail -f logs/*.log | grep -i error

# Monitor logs for specific pattern
tail -f logs/*.log | grep "operation_id"
```

### Check Service Metrics

```bash
# API Gateway metrics (if Prometheus enabled)
curl http://localhost:9090/metrics

# Celery inspect
cd orchestrator
source venv/Scripts/activate
celery -A config inspect active
celery -A config inspect stats
celery -A config inspect registered
cd ..
```

---

## Database Operations

### Backup Database

```bash
# Full backup
docker-compose -f docker-compose.local.yml exec postgres \
    pg_dump -U commandcenter commandcenter > backup_$(date +%Y%m%d_%H%M%S).sql

# Schema only
docker-compose -f docker-compose.local.yml exec postgres \
    pg_dump -U commandcenter --schema-only commandcenter > schema.sql

# Data only
docker-compose -f docker-compose.local.yml exec postgres \
    pg_dump -U commandcenter --data-only commandcenter > data.sql
```

### Restore Database

```bash
# Restore from backup
docker-compose -f docker-compose.local.yml exec -T postgres \
    psql -U commandcenter commandcenter < backup.sql

# Restore specific table
docker-compose -f docker-compose.local.yml exec -T postgres \
    psql -U commandcenter commandcenter -c "TRUNCATE TABLE operations CASCADE;"
docker-compose -f docker-compose.local.yml exec -T postgres \
    psql -U commandcenter commandcenter < operations_table.sql
```

### Database Queries

```bash
# Connect to database
docker exec -it postgres psql -U commandcenter -d commandcenter

# Common queries
SELECT COUNT(*) FROM operations;
SELECT * FROM operations WHERE status = 'pending' LIMIT 10;
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';

# Analyze query performance
EXPLAIN ANALYZE SELECT * FROM operations WHERE status = 'pending';
```

---

## Log Analysis

### Advanced Log Analysis

```bash
# Ошибки в логах Orchestrator
grep ERROR logs/orchestrator.log

# Последние 100 строк с ошибками
tail -n 100 logs/orchestrator.log | grep -i error

# Логи за последний час (если есть timestamps)
tail -n 1000 logs/api-gateway.log | grep "$(date +%H:)"

# Логи всех сервисов с фильтром
grep -i "connection refused" logs/*.log

# Следить за логами нескольких сервисов
tail -f logs/orchestrator.log logs/api-gateway.log

# Count errors by type
grep ERROR logs/*.log | cut -d':' -f3 | sort | uniq -c | sort -rn

# Find slow requests (if logged)
grep "duration" logs/api-gateway.log | awk '$8 > 1000' | head -20
```

### Docker Service Logs

```bash
# PostgreSQL
docker-compose -f docker-compose.local.yml logs postgres

# Redis
docker-compose -f docker-compose.local.yml logs redis

# Follow mode
docker-compose -f docker-compose.local.yml logs -f postgres

# Last 100 lines
docker-compose -f docker-compose.local.yml logs --tail=100 redis

# Since timestamp
docker-compose -f docker-compose.local.yml logs --since="2024-01-01T00:00:00"

# Grep logs
docker-compose -f docker-compose.local.yml logs postgres | grep ERROR
```

---

## Environment Configuration

### Multiple Environments

```bash
# Development (default)
cp .env.local.example .env.local

# Staging (local но production-like)
cp .env.local.example .env.staging
# Edit .env.staging:
# DEBUG=False
# LOG_LEVEL=warning

# Load staging environment
export ENV_FILE=.env.staging
./scripts/dev/start-all.sh
```

### Environment Validation

```bash
# Check all required variables
cd orchestrator
source venv/Scripts/activate
python manage.py check

# Validate .env.local
cat .env.local | grep -E "(DB_HOST|REDIS_HOST|DJANGO_SECRET_KEY)"

# Compare environments
diff .env.local .env.local.example
```

---

## Testing Workflows

### Load Testing

```bash
# Install Apache Bench
sudo apt-get install apache2-utils  # Linux
brew install apache2-utils  # Mac

# Test API Gateway health endpoint
ab -n 1000 -c 10 http://localhost:8080/health

# Test Orchestrator endpoint
ab -n 100 -c 5 -H "Authorization: Bearer TOKEN" \
    http://localhost:8000/api/operations/

# Install wrk for better performance
git clone https://github.com/wg/wrk.git
cd wrk && make

# Run wrk test
wrk -t4 -c100 -d30s http://localhost:8080/health
```

### Integration Testing

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
cd orchestrator
pytest tests/integration/

# Run E2E tests
cd ../frontend
npm run test:e2e

# Cleanup
docker-compose -f docker-compose.test.yml down -v
```

---

## Network Debugging

```bash
# Check all listening ports
netstat -ano | findstr LISTENING  # Windows
lsof -i -P | grep LISTEN  # Linux/Mac

# Check specific service ports
netstat -ano | findstr :8080  # API Gateway
netstat -ano | findstr :8000  # Orchestrator
netstat -ano | findstr :5173  # Frontend

# Test connectivity
curl -v http://localhost:8080/health
curl -v http://localhost:8000/health
curl -v http://localhost:8088/health

# Check DNS resolution (if using domains)
nslookup localhost
ping localhost

# Trace route (if remote services)
traceroute <hostname>  # Linux/Mac
tracert <hostname>  # Windows
```

---

## Git Workflows for Development

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes, restart service
./scripts/dev/restart.sh orchestrator

# Run tests
cd orchestrator && pytest && cd ..

# Commit changes
git add .
git commit -m "feat: implement my feature"

# Update from main
git fetch origin
git rebase origin/master

# Resolve conflicts if any
./scripts/dev/restart.sh orchestrator
./scripts/dev/health-check.sh

# Push
git push origin feature/my-feature
```

---

## Common Scenarios

### Scenario 1: Fresh Start After Git Pull

```bash
# Pull latest changes
git pull

# Update Python dependencies (if changed)
cd orchestrator
source venv/Scripts/activate
pip install -r requirements.txt
cd ..

# Update Node.js dependencies (if changed)
cd frontend
npm install
cd ..

# Update Go dependencies (if changed)
cd go-services/api-gateway
go mod download
cd ../..

# Run migrations (if any)
cd orchestrator
python manage.py migrate
cd ..

# Restart all services
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh

# Check health
./scripts/dev/health-check.sh
```

### Scenario 2: Debugging Production Issue Locally

```bash
# Reproduce issue locally
./scripts/dev/start-all.sh

# Enable debug logging in .env.local
echo "LOG_LEVEL=debug" >> .env.local

# Restart affected service
./scripts/dev/restart.sh orchestrator

# Follow logs in real-time
./scripts/dev/logs.sh orchestrator

# Test the issue
curl -X POST http://localhost:8000/api/operations \
    -H "Content-Type: application/json" \
    -d '{"operation": "test"}'

# Check logs for errors
grep ERROR logs/orchestrator.log

# Analyze request/response
tail -f logs/orchestrator.log | grep "operation_id"
```

### Scenario 3: Testing Database Migration

```bash
# Backup database first
docker-compose -f docker-compose.local.yml exec postgres \
    pg_dump -U commandcenter commandcenter > backup.sql

# Create migration
cd orchestrator
source venv/Scripts/activate
python manage.py makemigrations

# Check migration SQL
python manage.py sqlmigrate <app> <migration_number>

# Apply migration
python manage.py migrate

# Test migration
python manage.py shell
>>> from apps.operations.models import Operation
>>> Operation.objects.all()

# If something goes wrong - restore
docker-compose -f docker-compose.local.yml exec -T postgres \
    psql -U commandcenter commandcenter < backup.sql
```

### Scenario 4: Performance Profiling

```bash
# Profile Go service
cd go-services/api-gateway

# Build with profiling
go build -o ../../bin/cc1c-api-gateway.exe cmd/main.go

# Run with CPU profiling
./../../bin/cc1c-api-gateway.exe -cpuprofile=cpu.prof

# Generate some load
ab -n 10000 -c 100 http://localhost:8080/health

# Analyze profile
go tool pprof cpu.prof
# In pprof console:
# (pprof) top10
# (pprof) list main.handleRequest
# (pprof) web  # generates SVG graph
```
