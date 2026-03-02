// =============================================================================
// AUTO-GENERATED FILE - DO NOT EDIT MANUALLY
// =============================================================================
// Source: config/services.json
// Generated: 2026-03-02 20:58:50
// Mode: local
// Generator: scripts/config/generate.py
// =============================================================================


package ports

import "fmt"

// Service ports
const (
	Frontend = 15173
	ApiGateway = 8180
	Orchestrator = 8200
	Worker = 9191
	WorkerWorkflows = 9092
)

// Infrastructure ports
const (
	Postgresql = 5432
	Redis = 6379
	Minio = 9000
	Clickhouse = 8123
	Prometheus = 9090
	Grafana = 5000
	Jaeger = 16686
	Ras = 1645
)

// Default service URLs (for config fallbacks)
const (
	DefaultFrontendURL = "http://localhost:15173"
	DefaultApiGatewayURL = "http://localhost:8180"
	DefaultOrchestratorURL = "http://localhost:8200"
	DefaultWorkerURL = "http://localhost:9191"
)

// ServiceURLs maps service names to their URLs
var ServiceURLs = map[string]string{
	"frontend": "http://localhost:15173",
	"api-gateway": "http://localhost:8180",
	"orchestrator": "http://localhost:8200",
	"worker": "http://localhost:9191",
	"worker-workflows": "http://localhost:9092",
}

// ServiceHealthPaths maps service names to their health check paths
var ServiceHealthPaths = map[string]string{
	"api-gateway": "/health",
	"orchestrator": "/health",
	"worker": "/health",
	"worker-workflows": "/health",
}

// Address builders for http.ListenAndServe
func FrontendAddr() string { return fmt.Sprintf(":%d", Frontend) }
func ApiGatewayAddr() string { return fmt.Sprintf(":%d", ApiGateway) }
func OrchestratorAddr() string { return fmt.Sprintf(":%d", Orchestrator) }
func WorkerAddr() string { return fmt.Sprintf(":%d", Worker) }
