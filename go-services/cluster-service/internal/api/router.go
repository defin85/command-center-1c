package api

import (
	"github.com/command-center-1c/cluster-service/internal/api/handlers"
	"github.com/command-center-1c/cluster-service/internal/api/middleware"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

func SetupRouter(monitoringHandler *handlers.MonitoringHandler, logger *zap.Logger) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)

	router := gin.New()

	// Middleware
	router.Use(middleware.Recovery(logger))
	router.Use(middleware.Logger(logger))
	// EndpointID middleware УДАЛЁН - теперь используется gRPC interceptor

	// Health check
	healthHandler := handlers.NewHealthHandler()
	router.GET("/health", healthHandler.Health)

	// Session handler for session termination integration (P3.3)
	sessionsHandler := handlers.NewSessionsHandler(logger)

	// API routes
	v1 := router.Group("/api/v1")
	{
		v1.GET("/clusters", monitoringHandler.GetClusters)
		v1.GET("/infobases", monitoringHandler.GetInfobases)

		// Session management endpoints (MOCK for P3.3)
		v1.GET("/sessions", sessionsHandler.GetSessions)
		v1.POST("/sessions/terminate", sessionsHandler.TerminateSessions)
	}

	return router
}
