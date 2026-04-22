package routes

import (
	"github.com/commandcenter1c/commandcenter/api-gateway/internal/handlers"
	"github.com/commandcenter1c/commandcenter/api-gateway/internal/routes/generated"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/gin-gonic/gin"
)

// SSE routes that require special streaming proxy (FlushInterval for Server-Sent Events)
var sseRoutes = map[string]bool{
	"/operations/stream/": true,
	"/databases/stream/":  true,
}

// Streaming routes stay on a dedicated special-case path because reconnect storms are
// operationally different from regular request budgets.
var streamingRoutes = map[string]bool{
	"/operations/stream/":            true,
	"/operations/stream-ticket/":     true,
	"/operations/stream-mux/":        true,
	"/operations/stream-mux-ticket/": true,
	"/databases/stream/":             true,
	"/databases/stream-ticket/":      true,
}

var explicitRouteBudgetClasses = map[string]config.GatewayRateLimitClass{
	routeBudgetKey("GET", "/system/bootstrap/"):                    config.GatewayRateLimitClassShellCritical,
	routeBudgetKey("GET", "/system/me/"):                           config.GatewayRateLimitClassShellCritical,
	routeBudgetKey("GET", "/tenants/list-my-tenants/"):             config.GatewayRateLimitClassShellCritical,
	routeBudgetKey("GET", "/rbac/get-effective-access/"):           config.GatewayRateLimitClassShellCritical,
	routeBudgetKey("GET", "/settings/command-schemas/audit/"):      config.GatewayRateLimitClassShellCritical,
	routeBudgetKey("GET", "/pools/master-data/sync-status/"):       config.GatewayRateLimitClassBackground,
	routeBudgetKey("GET", "/pools/master-data/sync-conflicts/"):    config.GatewayRateLimitClassBackground,
	routeBudgetKey("GET", "/pools/master-data/sync-launches/"):     config.GatewayRateLimitClassBackground,
	routeBudgetKey("GET", "/pools/master-data/sync-launches/:id/"): config.GatewayRateLimitClassBackground,
	routeBudgetKey("POST", "/ui/incident-telemetry/ingest/"):       config.GatewayRateLimitClassTelemetry,
}

type OrchestratorRouteGroups struct {
	ShellCritical *gin.RouterGroup
	Interactive   *gin.RouterGroup
	Background    *gin.RouterGroup
	Telemetry     *gin.RouterGroup
	Streaming     *gin.RouterGroup
	DefaultClass  config.GatewayRateLimitClass
}

func routeBudgetKey(method, path string) string {
	return method + " " + path
}

func resolveOrchestratorRouteBudgetClass(
	method string,
	path string,
	defaultClass config.GatewayRateLimitClass,
) config.GatewayRateLimitClass {
	if streamingRoutes[path] {
		return config.GatewayRateLimitClassStreaming
	}
	if explicitClass, ok := explicitRouteBudgetClasses[routeBudgetKey(method, path)]; ok {
		return explicitClass
	}
	return config.NormalizeGatewayRateLimitClass(string(defaultClass), config.GatewayRateLimitClassInteractive)
}

func groupForBudgetClass(
	groups OrchestratorRouteGroups,
	budgetClass config.GatewayRateLimitClass,
) *gin.RouterGroup {
	switch budgetClass {
	case config.GatewayRateLimitClassShellCritical:
		return groups.ShellCritical
	case config.GatewayRateLimitClassBackground:
		return groups.Background
	case config.GatewayRateLimitClassTelemetry:
		return groups.Telemetry
	case config.GatewayRateLimitClassStreaming:
		return groups.Streaming
	default:
		return groups.Interactive
	}
}

// RegisterOrchestratorRoutes registers routes to proxy to Django Orchestrator.
// Routes are auto-generated from Django OpenAPI spec (contracts/orchestrator/openapi.yaml).
// To add new routes: add endpoint in Django API v2 -> run generate-all.sh -> rebuild.
func RegisterOrchestratorRoutes(groups OrchestratorRouteGroups, handler gin.HandlerFunc) {
	for _, route := range generated.OrchestratorRoutes {
		// Use SSE proxy for streaming routes (requires FlushInterval)
		routeHandler := handler
		if sseRoutes[route.Path] {
			routeHandler = handlers.SSEOperationStreamProxy
		}

		targetGroup := groupForBudgetClass(
			groups,
			resolveOrchestratorRouteBudgetClass(route.Method, route.Path, groups.DefaultClass),
		)

		switch route.Method {
		case "GET":
			targetGroup.GET(route.Path, routeHandler)
		case "POST":
			targetGroup.POST(route.Path, routeHandler)
		case "PUT":
			targetGroup.PUT(route.Path, routeHandler)
		case "PATCH":
			targetGroup.PATCH(route.Path, routeHandler)
		case "DELETE":
			targetGroup.DELETE(route.Path, routeHandler)
		case "HEAD":
			targetGroup.HEAD(route.Path, routeHandler)
		case "OPTIONS":
			targetGroup.OPTIONS(route.Path, routeHandler)
		}
	}
}
