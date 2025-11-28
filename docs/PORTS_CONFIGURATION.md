# Ports Configuration

> Централизованная конфигурация портов для CommandCenter1C

## Problem

Windows Hyper-V/WSL резервирует динамические порты в диапазонах:
- **7913-8012** (старый диапазон)
- **8013-8112** (новый диапазон)

Это вызывает ошибки `bind: An attempt was made to access a socket in a way forbidden by its access permissions`.

## Solution

Все порты перенесены в безопасный диапазон **8180-8200** и **5xxx**.

## Port Mapping

| Service | Old Port | New Port | Environment Variable |
|---------|----------|----------|---------------------|
| **Frontend** | 5173 | 5173 | - |
| **API Gateway** | 8080 | **8180** | `SERVER_PORT` |
| **Orchestrator** | 8000 | **8200** | `ORCHESTRATOR_PORT` |
| **RAS Adapter** | 8088 | **8188** | `RAS_ADAPTER_PORT` |
| **Batch Service** | 8087 | **8187** | `BATCH_SERVICE_PORT` |
| **Installation Service** | 8085 | **8185** | `INSTALLATION_SERVICE_PORT` |
| **Worker** | 9091 | 9091 | - |

### Infrastructure (Docker)

| Service | Port | Notes |
|---------|------|-------|
| PostgreSQL | 5432 | Standard |
| Redis | 6379 | Standard |
| ClickHouse | 8123, 9000 | HTTP, Native |
| Prometheus | 9090 | Standard |
| Grafana | 5000 | Changed from 3000 |
| Jaeger | 16686 | Standard |
| RAS (1C) | 1545 | Standard |

## Configuration Files

### Primary Sources (edit these)

1. **`.env.local`** - Main environment file
   ```bash
   SERVER_PORT=8180
   ORCHESTRATOR_PORT=8200
   RAS_ADAPTER_PORT=8188
   BATCH_SERVICE_PORT=8187
   ```

2. **`orchestrator/config/settings/base.py`** - Django defaults
   ```python
   API_GATEWAY_URL = env('API_GATEWAY_URL', default='http://localhost:8180')
   RAS_ADAPTER_URL = env('RAS_ADAPTER_URL', default='http://localhost:8188')
   BATCH_SERVICE_URL = env('BATCH_SERVICE_URL', default='http://localhost:8187')
   ```

3. **`go-services/shared/config/config.go`** - Go defaults
   ```go
   OrchestratorURL: getEnv("ORCHESTRATOR_URL", "http://localhost:8200"),
   RASAdapterURL: getEnv("RAS_ADAPTER_URL", "http://localhost:8188"),
   ```

4. **`frontend/.env.local`** - Frontend API URL
   ```bash
   VITE_API_URL=http://localhost:8180/api/v2
   VITE_WS_HOST=localhost:8200
   ```

### Secondary Files (auto-derived)

These files use environment variables or settings from primary sources:
- `scripts/dev/*.sh` - Use variables from `.env.local`
- Django views - Use `settings.RAS_ADAPTER_URL` etc.
- Go services - Use `config.GetConfig()`

## Adding a New Service

1. Choose port in range **8180-8199** or **9xxx**
2. Add to `.env.local`:
   ```bash
   NEW_SERVICE_PORT=8189
   NEW_SERVICE_URL=http://localhost:8189
   ```
3. Add to `orchestrator/config/settings/base.py`:
   ```python
   NEW_SERVICE_URL = env('NEW_SERVICE_URL', default='http://localhost:8189')
   ```
4. Add to `go-services/shared/config/config.go` if needed
5. Update `scripts/dev/health-check.sh`

## Troubleshooting

### Check for Reserved Ports

```powershell
# PowerShell - show reserved ranges
netsh interface ipv4 show excludedportrange protocol=tcp
```

### Find Hardcoded Ports

```bash
# Find old ports in codebase
grep -rn "localhost:808[0-9]" --include="*.py" --include="*.go" --include="*.ts"
```

### Verify Current Configuration

```bash
./scripts/dev/health-check.sh
```

## Migration History

- **2024-11-28**: Migrated from 8080/8087/8088 to 8180/8187/8188
- Reason: Windows Hyper-V reserved port ranges
