---
description: Check health status of all running services
---

Проверить статус здоровья всех работающих сервисов.

## Действия

1. **Проверить Docker контейнеры**
   ```bash
   docker-compose ps
   ```

2. **Проверить API Gateway**
   ```bash
   curl -s http://localhost:8080/health | jq .
   ```

3. **Проверить Orchestrator**
   ```bash
   curl -s http://localhost:8000/health | jq .
   ```

4. **Проверить Frontend**
   ```bash
   curl -s http://localhost:3000 -I
   ```

5. **Проверить Redis**
   ```bash
   docker-compose exec redis redis-cli ping
   ```

6. **Проверить PostgreSQL**
   ```bash
   docker-compose exec postgres psql -U orchestrator -d command_center -c "SELECT 1"
   ```

7. **Проверить логи ошибок**
   ```bash
   docker-compose logs --tail=50 | grep ERROR
   ```

## Примеры

```bash
# Все at once
make check-health

# Конкретный сервис
docker-compose logs api-gateway
docker-compose logs orchestrator

# Полные логи для отладки
docker-compose logs --tail=100 api-gateway

# Real-time logs
docker-compose logs -f orchestrator

# Логи за последний час
docker-compose logs --since 1h api-gateway
```

## Ожидаемые результаты

**API Gateway (8080):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": "2h 30m"
}
```

**Orchestrator (8000):**
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected"
}
```

**Frontend (3000):**
```
HTTP/1.1 200 OK
```

**Redis:**
```
PONG
```

**PostgreSQL:**
```
 ?column?
----------
        1
```

## Troubleshooting

**Service not responding:**
```bash
# Check logs
docker-compose logs <service-name>

# Restart service
docker-compose restart <service-name>

# Full restart
docker-compose down && docker-compose up -d
```

**Connection refused:**
```bash
# Check if port is listening
lsof -i :<port>

# Check firewall (on WSL2)
netstat -tuln | grep <port>
```

**Database connection error:**
```bash
# Check PostgreSQL container
docker-compose logs postgres

# Check credentials
docker-compose exec postgres psql -U orchestrator -d command_center
```

**Redis not responding:**
```bash
# Check Redis logs
docker-compose logs redis

# Test connection
docker-compose exec redis redis-cli PING
```

## Metrics (Optional)

```bash
# Check resource usage
docker stats

# Check disk usage
docker system df

# Check network
docker network inspect command-center_default
```

## Связанные Commands

- `dev-start` - запустить сервисы
- `test-all` - запустить тесты
- `docker-logs` - просмотреть логи в detail
