package rest

import (
	v2 "github.com/commandcenter1c/commandcenter/ras-adapter/internal/api/rest/v2"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/api/middleware"
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

	// API v2 routes (action-based) - v1 removed after migration complete
	apiV2 := router.Group("/api/v2")
	v2.SetupRoutes(apiV2, clusterSvc, infobaseSvc, sessionSvc)

	return router
}
