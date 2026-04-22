# Environment variables for feature/unified-workflow-platform worktree
# Ports shifted to avoid conflicts with main worktree

# Django Settings
DJANGO_SECRET_KEY=workflow-dev-secret-key
DJANGO_SETTINGS_MODULE=config.settings.development
DEBUG=True
ALLOWED_HOSTS=*

# Database encryption key
DB_ENCRYPTION_KEY=your-generated-key-here

# Database (PostgreSQL) - Isolated instance
DB_HOST=localhost
DB_PORT=5532  # +100 offset from main (5432)
DB_NAME=commandcenter_workflow
DB_USER=commandcenter
DB_PASSWORD=dev_password_change_in_prod
DB_SSLMODE=disable

# Redis - Isolated instance
REDIS_HOST=localhost
REDIS_PORT=6479  # +100 offset from main (6379)
REDIS_DB=0
REDIS_PASSWORD=

# Go Services - Shifted ports
SERVER_HOST=0.0.0.0
SERVER_PORT=8180  # API Gateway: +100 offset (was 8080)
ORCHESTRATOR_URL=http://localhost:8100  # Orchestrator: +100 offset (was 8000)
INTERNAL_API_TOKEN=dev-internal-token-change-in-production

# JWT
JWT_SECRET=workflow-jwt-secret
JWT_EXPIRE_TIME=24h
JWT_ISSUER=commandcenter1c-workflow

# Worker
WORKER_POOL_SIZE=50
WORKER_MAX_RETRIES=3
WORKER_TIMEOUT=5m
ENABLE_GO_SCHEDULER=true
ENABLE_POOLOPS_ROUTE=true
POOLOPS_ROUTE_ROLLOUT_PERCENT=1.0
POOLOPS_ROUTE_ROLLOUT_SEED=
POOLOPS_ROUTE_KILL_SWITCH=false
ENABLE_POOL_PUBLICATION_ODATA_CORE=true
POOL_PUBLICATION_ODATA_CORE_ROLLOUT_PERCENT=1.0
POOL_PUBLICATION_ODATA_CORE_ROLLOUT_SEED=
POOL_PUBLICATION_ODATA_CORE_KILL_SWITCH=false
# Projection hardening cutoff is configured in Orchestrator runtime settings:
# pools.projection.publication_hardening_cutoff_utc

# Logging
LOG_LEVEL=debug  # More verbose for development
LOG_FORMAT=text

# Metrics
METRICS_ENABLED=true
METRICS_PORT=9190  # Prometheus: +100 offset (was 9090)

# API Gateway request budget isolation
API_GATEWAY_RATE_LIMIT_DEFAULT_CLASS=interactive
API_GATEWAY_RATE_LIMIT_SHELL_CRITICAL_REQUESTS=60
API_GATEWAY_RATE_LIMIT_SHELL_CRITICAL_WINDOW=1m
API_GATEWAY_RATE_LIMIT_INTERACTIVE_REQUESTS=100
API_GATEWAY_RATE_LIMIT_INTERACTIVE_WINDOW=1m
API_GATEWAY_RATE_LIMIT_BACKGROUND_HEAVY_REQUESTS=50
API_GATEWAY_RATE_LIMIT_BACKGROUND_HEAVY_WINDOW=1m
API_GATEWAY_RATE_LIMIT_TELEMETRY_REQUESTS=20
API_GATEWAY_RATE_LIMIT_TELEMETRY_WINDOW=1m

# Frontend
VITE_API_URL=http://localhost:8180/api/v1  # API Gateway shifted port
VITE_WS_URL=ws://localhost:8180/ws

# Installation Service
INSTALLATION_SERVICE_URL=http://localhost:8185  # +100 offset (was 8085)
INSTALLATION_SERVICE_TIMEOUT=180

# RAS gRPC Gateway
RAS_SERVER=192.168.32.143:1645
GRPC_GATEWAY_ADDR=localhost:10099  # +100 offset (was 9999)
GRPC_CONN_TIMEOUT=5s
GRPC_REQUEST_TIMEOUT=10s

# Cluster Service
CLUSTER_SERVICE_URL=http://localhost:8188  # +100 offset (was 8088)
CLUSTER_SERVICE_TIMEOUT=30
