package api

import (
	"time"

	"github.com/commandcenter1c/commandcenter/installation-service/internal/api/handlers"
	"github.com/commandcenter1c/commandcenter/installation-service/internal/config"
	"github.com/gin-gonic/gin"
)

// SetupRouter configures and returns the Gin router
func SetupRouter(cfg *config.Config) *gin.Engine {
	router := gin.New()

	// Global middleware
	router.Use(gin.Recovery())
	router.Use(gin.Logger())

	// Health check endpoints (no auth required)
	router.GET("/health", handlers.HealthCheck)
	router.GET("/ready", handlers.ReadyCheck)

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Infobases handler
		infobasesHandler := handlers.NewInfobasesHandler(
			cfg.RAC.Path,
			time.Duration(cfg.RAC.TimeoutSeconds)*time.Second,
		)

		// Infobases endpoint
		v1.GET("/infobases", infobasesHandler.GetInfobases)
	}

	return router
}
