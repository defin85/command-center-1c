// =============================================================================
// AUTO-GENERATED FILE - DO NOT EDIT MANUALLY
// =============================================================================
// Source: config/services.json
// Generated: 2025-12-19 21:09:53
// Mode: local
// Generator: scripts/config/generate.py
// =============================================================================


package ports

import "fmt"

// Service ports
const (
	Frontend = 5173
	ApiGateway = 8180
	Orchestrator = 8200
	RasAdapter = 8188
	DesignerAgent = 8190
	BatchService = 8187
	Worker = 9091
)

// Infrastructure ports
const (
	Postgresql = 5432
	Redis = 6379
	Clickhouse = 8123
	Prometheus = 9090
	Grafana = 5000
	Jaeger = 16686
	Ras = 1545
)

// Default service URLs (for config fallbacks)
const (
	DefaultFrontendURL = "http://localhost:5173"
	DefaultApiGatewayURL = "http://localhost:8180"
	DefaultOrchestratorURL = "http://localhost:8200"
	DefaultRasAdapterURL = "http://localhost:8188"
	DefaultDesignerAgentURL = "http://localhost:8190"
	DefaultBatchServiceURL = "http://localhost:8187"
	DefaultWorkerURL = "http://localhost:9091"
)

// ServiceURLs maps service names to their URLs
var ServiceURLs = map[string]string{
	"frontend": "http://localhost:5173",
	"api-gateway": "http://localhost:8180",
	"orchestrator": "http://localhost:8200",
	"ras-adapter": "http://localhost:8188",
	"designer-agent": "http://localhost:8190",
	"batch-service": "http://localhost:8187",
	"worker": "http://localhost:9091",
}

// ServiceHealthPaths maps service names to their health check paths
var ServiceHealthPaths = map[string]string{
	"api-gateway": "/health",
	"orchestrator": "/health",
	"ras-adapter": "/health",
	"designer-agent": "/health",
	"batch-service": "/health",
	"worker": "/health",
}

// Address builders for http.ListenAndServe
func FrontendAddr() string { return fmt.Sprintf(":%d", Frontend) }
func ApiGatewayAddr() string { return fmt.Sprintf(":%d", ApiGateway) }
func OrchestratorAddr() string { return fmt.Sprintf(":%d", Orchestrator) }
func RasAdapterAddr() string { return fmt.Sprintf(":%d", RasAdapter) }
func DesignerAgentAddr() string { return fmt.Sprintf(":%d", DesignerAgent) }
func BatchServiceAddr() string { return fmt.Sprintf(":%d", BatchService) }
func WorkerAddr() string { return fmt.Sprintf(":%d", Worker) }
