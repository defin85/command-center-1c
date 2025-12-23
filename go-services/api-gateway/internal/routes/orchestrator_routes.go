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

// RegisterOrchestratorRoutes registers routes to proxy to Django Orchestrator.
// Routes are auto-generated from Django OpenAPI spec (contracts/orchestrator/openapi.yaml).
// To add new routes: add endpoint in Django API v2 -> run generate-all.sh -> rebuild.
func RegisterOrchestratorRoutes(rg *gin.RouterGroup, handler gin.HandlerFunc) {
	for _, route := range generated.OrchestratorRoutes {
		// Use SSE proxy for streaming routes (requires FlushInterval)
		routeHandler := handler
		if sseRoutes[route.Path] {
			routeHandler = handlers.SSEOperationStreamProxy
		}

		switch route.Method {
		case "GET":
			rg.GET(route.Path, routeHandler)
		case "POST":
			rg.POST(route.Path, routeHandler)
		case "PUT":
			rg.PUT(route.Path, routeHandler)
		case "PATCH":
			rg.PATCH(route.Path, routeHandler)
		case "DELETE":
			rg.DELETE(route.Path, routeHandler)
		case "HEAD":
			rg.HEAD(route.Path, routeHandler)
		case "OPTIONS":
			rg.OPTIONS(route.Path, routeHandler)
		}
	}
}
