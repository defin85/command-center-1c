package rest

import (
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/api/middleware"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// NewRouter creates a new Gin router with all routes configured
func NewRouter(
	clusterSvc *service.ClusterService,
	infobaseSvc *service.InfobaseService,
	sessionSvc *service.SessionService,
	logger *zap.Logger,
) *gin.Engine {
	router := gin.New()

	// Global middleware
	router.Use(middleware.Logger(logger))
	router.Use(middleware.Recovery(logger))

	// Health check endpoint
	router.GET("/health", Health())

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Cluster routes
		v1.GET("/clusters", GetClusters(clusterSvc))
		v1.GET("/clusters/:id", GetClusterByID(clusterSvc))

		// Infobase routes
		v1.GET("/infobases", GetInfobases(infobaseSvc))
		v1.GET("/infobases/:id", GetInfobaseByID(infobaseSvc))
		v1.POST("/infobases", CreateInfobase(infobaseSvc))
		v1.DELETE("/infobases/:id", DropInfobase(infobaseSvc))
		v1.POST("/infobases/:infobase_id/lock", LockInfobase(infobaseSvc))
		v1.POST("/infobases/:infobase_id/unlock", UnlockInfobase(infobaseSvc))

		// Session routes
		v1.GET("/sessions", GetSessions(sessionSvc))
		v1.POST("/sessions/terminate", TerminateSessions(sessionSvc))
	}

	return router
}
