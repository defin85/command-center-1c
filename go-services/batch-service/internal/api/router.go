package api

import (
	"github.com/gin-gonic/gin"
	"github.com/command-center-1c/batch-service/internal/api/handlers"
	"github.com/command-center-1c/batch-service/internal/service"
)

// SetupRouter configures and returns a Gin router with all routes
func SetupRouter(extensionInstaller *service.ExtensionInstaller) *gin.Engine {
	router := gin.Default()

	// Create handlers
	extensionsHandler := handlers.NewExtensionsHandler(extensionInstaller)

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Extension endpoints
		extensions := v1.Group("/extensions")
		{
			extensions.POST("/install", extensionsHandler.InstallExtension)
			extensions.POST("/batch-install", extensionsHandler.BatchInstall)
		}
	}

	// Health check endpoint
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status":  "healthy",
			"service": "batch-service",
			"version": "1.0.0",
		})
	})

	return router
}
