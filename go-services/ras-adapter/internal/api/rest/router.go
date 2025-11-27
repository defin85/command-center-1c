package rest

import (
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/api/middleware"
	v2 "github.com/commandcenter1c/commandcenter/ras-adapter/internal/api/rest/v2"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
	"github.com/gin-gonic/gin"
	swaggerFiles "github.com/swaggo/files"
	ginSwagger "github.com/swaggo/gin-swagger"
	"go.uber.org/zap"

	_ "github.com/commandcenter1c/commandcenter/ras-adapter/docs" // swagger docs
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

	// Swagger UI
	router.GET("/swagger/*any", ginSwagger.WrapHandler(swaggerFiles.Handler))

	// API v1 routes (legacy, deprecated - sunset 2026-03-01)
	apiV1 := router.Group("/api/v1")
	apiV1.Use(middleware.Deprecation(middleware.DefaultDeprecationConfig(logger)))
	{
		// Cluster routes
		apiV1.GET("/clusters", GetClusters(clusterSvc))
		apiV1.GET("/clusters/:id", GetClusterByID(clusterSvc))

		// Infobase routes
		apiV1.GET("/infobases", GetInfobases(infobaseSvc))
		apiV1.GET("/infobases/:id", GetInfobaseByID(infobaseSvc))
		apiV1.POST("/infobases", CreateInfobase(infobaseSvc))
		apiV1.DELETE("/infobases/:id", DropInfobase(infobaseSvc))
		apiV1.POST("/infobases/:infobase_id/lock", LockInfobase(infobaseSvc))
		apiV1.POST("/infobases/:infobase_id/unlock", UnlockInfobase(infobaseSvc))
		apiV1.POST("/infobases/:infobase_id/block-sessions", BlockSessions(infobaseSvc))
		apiV1.POST("/infobases/:infobase_id/unblock-sessions", UnblockSessions(infobaseSvc))

		// Session routes
		apiV1.GET("/sessions", GetSessions(sessionSvc))
		apiV1.POST("/sessions/terminate", TerminateSessions(sessionSvc))
	}

	// API v2 routes (action-based)
	apiV2 := router.Group("/api/v2")
	v2.SetupRoutes(apiV2, clusterSvc, infobaseSvc, sessionSvc)

	return router
}
