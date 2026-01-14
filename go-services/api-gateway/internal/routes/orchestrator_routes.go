package routes

import (
	"github.com/commandcenter1c/commandcenter/api-gateway/internal/handlers"
	"github.com/commandcenter1c/commandcenter/api-gateway/internal/routes/generated"
	"github.com/gin-gonic/gin"
)

// SSE routes that require special streaming proxy (FlushInterval for Server-Sent Events)
var sseRoutes = map[string]bool{
	"/operations/stream/": true,
	"/databases/stream/":  true,
}

// Routes that should NOT be subject to global API rate limit.
// Rationale: stream and stream-ticket endpoints can legitimately reconnect frequently,
// and applying the same 100 req/min limit can block unrelated user actions.
var noRateLimitRoutes = map[string]bool{
	"/operations/stream/":            true,
	"/operations/stream-ticket/":     true,
	"/operations/stream-mux/":        true,
	"/operations/stream-mux-ticket/": true,
	"/databases/stream/":             true,
	"/databases/stream-ticket/":      true,
}

// RegisterOrchestratorRoutes registers routes to proxy to Django Orchestrator.
// Routes are auto-generated from Django OpenAPI spec (contracts/orchestrator/openapi.yaml).
// To add new routes: add endpoint in Django API v2 -> run generate-all.sh -> rebuild.
func RegisterOrchestratorRoutes(rgLimited *gin.RouterGroup, rgUnlimited *gin.RouterGroup, handler gin.HandlerFunc) {
	for _, route := range generated.OrchestratorRoutes {
		// Use SSE proxy for streaming routes (requires FlushInterval)
		routeHandler := handler
		if sseRoutes[route.Path] {
			routeHandler = handlers.SSEOperationStreamProxy
		}

		targetGroup := rgLimited
		if noRateLimitRoutes[route.Path] {
			targetGroup = rgUnlimited
		}

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
