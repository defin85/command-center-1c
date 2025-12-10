# Setup & Troubleshooting

> Первоначальная настройка и решение проблем.

## Prerequisites

- Python 3.11+, Go 1.21+, Node.js 18+
- **Native mode (WSL):** PostgreSQL, Redis via systemd
- **Docker mode:** Docker 20.10+, Docker Compose 2.0+

## Initial Setup

```bash
git clone <repo>
cd command-center-1c
cp .env.local.example .env.local
# Edit .env.local:
#   DB_HOST=localhost, REDIS_HOST=localhost
#   USE_DOCKER=false  # for Native mode (WSL/Linux)
#   USE_DOCKER=true   # for Docker mode

# Python
cd orchestrator && python -m venv venv
source venv/bin/activate && pip install -r requirements.txt && cd ..

# Node.js
cd frontend && npm install && cd ..

# Go (optional - auto-builds on start)
cd go-services/api-gateway && go mod download && cd ../..

# Start all
./scripts/dev/start-all.sh
```

## Native Mode (WSL/Arch Linux)

```bash
# Install and enable services
sudo pacman -S postgresql redis prometheus grafana
sudo systemctl enable --now postgresql redis

# Monitoring (optional)
sudo systemctl enable --now prometheus grafana
# Jaeger: yay -S jaeger (from AUR) or download binary
```

## Troubleshooting

### Database Connection Error

- Native: `systemctl status postgresql`, `pg_isready -h localhost`
- Docker: `docker ps`, `docker exec -it postgres pg_isready`

### Redis Connection Error

- Native: `systemctl status redis`, `redis-cli ping`
- Docker: `docker exec -it redis redis-cli ping`

### Grafana/Jaeger Shows connection_refused

- Native mode: Grafana on port **3000** (not 5000!)
- Check: `systemctl status grafana prometheus`
- Jaeger installation: `yay -S jaeger` or download from GitHub

### Monitoring Not Starting

- `./scripts/dev/start-monitoring.sh` - starts based on mode
- Native: check `systemctl status prometheus grafana`

## Build System

**Smart auto-rebuild:**
```bash
./scripts/dev/start-all.sh           # Smart start with auto-rebuild
./scripts/dev/start-all.sh --force-rebuild  # Force rebuild
./scripts/dev/restart-all.sh         # Smart restart
```

**How it works:**
1. Auto-detect changes (compares timestamps)
2. Selective rebuild ONLY changed services
3. Check `go-services/shared/` → rebuilds ALL if changed
4. ALWAYS uses binaries (NO `go run`)

**Binary format:** `bin/cc1c-<service-name>.exe`

**Full troubleshooting:** `docs/LOCAL_DEVELOPMENT_GUIDE.md#troubleshooting`
