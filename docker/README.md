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

Список контейнеров см. в `docker-compose.yml`.

## Troubleshooting

### Services not starting

```bash
# Check logs
docker-compose logs

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
docker-compose build api-gateway
docker-compose up -d api-gateway

# View real-time logs
docker-compose logs -f api-gateway
```
