package routes

import (
	"github.com/commandcenter1c/commandcenter/api-gateway/internal/routes/generated"
	"github.com/gin-gonic/gin"
)

// RegisterOrchestratorRoutes registers routes to proxy to Django Orchestrator.
// Routes are auto-generated from Django OpenAPI spec (contracts/orchestrator/openapi.yaml).
// To add new routes: add endpoint in Django API v2 -> run generate-all.sh -> rebuild.
func RegisterOrchestratorRoutes(rg *gin.RouterGroup, handler gin.HandlerFunc) {
	for _, route := range generated.OrchestratorRoutes {
		switch route.Method {
		case "GET":
			rg.GET(route.Path, handler)
		case "POST":
			rg.POST(route.Path, handler)
		case "PUT":
			rg.PUT(route.Path, handler)
		case "PATCH":
			rg.PATCH(route.Path, handler)
		case "DELETE":
			rg.DELETE(route.Path, handler)
		case "HEAD":
			rg.HEAD(route.Path, handler)
		case "OPTIONS":
			rg.OPTIONS(route.Path, handler)
		}
	}
}
