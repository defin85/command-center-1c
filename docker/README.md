# Docker Compose Setup

## Quick Start

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Services

### ras-grpc-gw
- **Port:** 9999 (gRPC), 8081 (health check)
- **Health:** http://localhost:8081/health
- **Image:** ras-grpc-gw:v1.0.0-cc

### cluster-service
- **Port:** 8088 (HTTP API)
- **Health:** http://localhost:8088/health
- **API:** http://localhost:8088/api/v1
- **Image:** cluster-service:v1.0.0-sprint1

## Testing

```bash
# Health checks
curl http://localhost:8081/health  # ras-grpc-gw
curl http://localhost:8088/health  # cluster-service

# Get clusters (requires RAS server)
curl "http://localhost:8088/api/v1/clusters?server=host.docker.internal:1545"

# Get infobases
curl "http://localhost:8088/api/v1/infobases?server=host.docker.internal:1545"
```

## Troubleshooting

### Services not starting

```bash
# Check logs
docker-compose logs ras-grpc-gw
docker-compose logs cluster-service

# Rebuild images
docker-compose build --no-cache
docker-compose up -d
```

### Connection refused to RAS

Check that RAS server is running on `localhost:1545`:
```bash
telnet localhost 1545
```

On Windows, use `host.docker.internal:1545` instead of `localhost:1545`.

## Development

```bash
# Rebuild specific service
docker-compose build cluster-service
docker-compose up -d cluster-service

# View real-time logs
docker-compose logs -f cluster-service
```
