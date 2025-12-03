# RAS Adapter

RAS Adapter - сервис для взаимодействия с 1C RAS (Remote Administration Server) через бинарный протокол.

## Статус разработки

**Week 1 (Foundation)** - ✅ IMPLEMENTED (Stub version)

- REST API для мониторинга (GET /clusters, /infobases, /sessions)
- Event handler для terminate sessions (Redis Pub/Sub)
- Health checks
- Stub implementation (mock data)

**Week 2+** - 🔲 TODO

- Real RAS binary protocol implementation
- Lock/Unlock operations через RegInfoBase
- Integration tests

## Архитектура

```
┌─────────────┐
│   REST API  │  HTTP endpoints
│   (Gin)     │
└──────┬──────┘
       │
┌──────▼──────┐
│   Service   │  Business logic
│   Layer     │
└──────┬──────┘
       │
┌──────▼──────┐
│ RAS Client  │  RAS binary protocol (Week 2+)
│   Pool      │  Connection pooling
└──────┬──────┘
       │
       ▼
   RAS Server (1C)
```

## REST API Endpoints

### Health Check

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "service": "ras-adapter"
}
```

### Get Clusters

```bash
GET /api/v1/clusters?server=localhost:1545
```

Response:
```json
{
  "clusters": [
    {
      "uuid": "...",
      "name": "Local Cluster",
      "host": "localhost",
      "port": 1541
    }
  ]
}
```

### Get Infobases

```bash
GET /api/v1/infobases?cluster_id=UUID
```

Response:
```json
{
  "infobases": [
    {
      "uuid": "...",
      "name": "test_db",
      "dbms": "PostgreSQL",
      "db_server": "localhost",
      "db_name": "test_db"
    }
  ]
}
```

### Get Sessions

```bash
GET /api/v1/sessions?cluster_id=UUID&infobase_id=UUID
```

Response:
```json
{
  "sessions": [
    {
      "uuid": "...",
      "session_id": "...",
      "user_name": "TestUser",
      "application": "1CV8C",
      "started_at": "2025-11-20T13:45:00Z"
    }
  ],
  "count": 1
}
```

### Terminate Sessions

```bash
POST /api/v1/sessions/terminate
Content-Type: application/json

{
  "infobase_id": "UUID",
  "session_ids": ["UUID1", "UUID2"]
}
```

Response:
```json
{
  "terminated_count": 2,
  "failed_sessions": []
}
```

## Event Handlers

### Terminate Sessions Command

**Channel:** `commands:cluster-service:sessions:terminate`

**Payload:**
```json
{
  "cluster_id": "UUID",
  "infobase_id": "UUID",
  "database_id": "123"
}
```

**Success Event:** `events:cluster-service:sessions:closed`

**Error Event:** `events:cluster-service:sessions:terminate-failed`

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_HOST` | `0.0.0.0` | HTTP server host |
| `SERVER_PORT` | `8088` | HTTP server port |
| `RAS_SERVER_ADDR` | `localhost:1545` | RAS server address |
| `RAS_MAX_CONNECTIONS` | `10` | Max RAS connections in pool |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PUBSUB_ENABLED` | `false` | Enable Redis Pub/Sub (default: disabled for safety) |
| `LOG_LEVEL` | `info` | Log level (debug, info, warn, error) |

## Build & Run

### Build

```bash
cd /c/1CProject/command-center-1c
./scripts/build.sh --service=ras-adapter
```

### Run

```bash
# Set environment
export RAS_SERVER_ADDR=localhost:1545
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Run
./bin/cc1c-ras-adapter
```

## Testing

### Unit Tests

```bash
cd go-services/ras-adapter
go test ./...
```

### Integration Tests

```bash
cd go-services/ras-adapter
go test ./tests/integration/...
```

### Manual API Testing

```bash
# Health check
curl http://localhost:8088/health

# Get clusters
curl "http://localhost:8088/api/v1/clusters?server=localhost:1545"

# Get infobases
curl "http://localhost:8088/api/v1/infobases?cluster_id=UUID"

# Get sessions
curl "http://localhost:8088/api/v1/sessions?cluster_id=UUID&infobase_id=UUID"

# Terminate sessions
curl -X POST http://localhost:8088/api/v1/sessions/terminate \
  -H "Content-Type: application/json" \
  -d '{"infobase_id": "UUID", "session_ids": ["UUID1"]}'
```

## Development Roadmap

### Week 1: Foundation ✅

- [x] Project structure setup
- [x] Config, models, middleware (copied from cluster-service)
- [x] Stub RAS client (mock data)
- [x] Service layer
- [x] REST API handlers
- [x] Event handlers (terminate only)
- [x] main.go integration
- [x] Build & compile

### Week 2: Real RAS Protocol 🔲

- [ ] Real RAS client via ras-grpc-gw
- [ ] Connection pooling
- [ ] Error handling & retries
- [ ] Lock/Unlock via RegInfoBase
- [ ] Integration tests

### Week 3: Production Ready 🔲

- [ ] Metrics (Prometheus)
- [ ] Graceful degradation
- [ ] Circuit breaker
- [ ] Rate limiting
- [ ] Performance testing

## Notes

**Week 1 Limitations:**

- **Stub implementation** - возвращает mock data
- **No real RAS connection** - для тестирования структуры API
- **Lock/Unlock NOT implemented** - будет в Week 2 через RegInfoBase

**Week 2 Changes:**

- Replace stub RAS client с real implementation
- Add connection pooling to RAS
- Implement Lock/Unlock через RegInfoBase (новая реализация)
