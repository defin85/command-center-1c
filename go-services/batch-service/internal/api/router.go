package api

import (
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"

	"github.com/command-center-1c/batch-service/internal/api/handlers"
	"github.com/command-center-1c/batch-service/internal/domain/metadata"
	"github.com/command-center-1c/batch-service/internal/domain/storage"
	"github.com/command-center-1c/batch-service/internal/metrics"
)

// SetupRouter configures and returns a Gin router with all routes
// NOTE: Most extension operations (install, delete, rollback, backups) are now
// handled via Redis Streams (Event-Driven Architecture). This HTTP API provides
// only storage operations for Orchestrator and metadata extraction.
func SetupRouter(
	storageManager *storage.Manager,
	metadataExtractor *metadata.Extractor,
	batchMetrics *metrics.BatchMetrics,
	logger *zap.Logger,
) *gin.Engine {
	router := gin.Default()

	// Add metrics middleware (skip /metrics and /health)
	router.Use(metrics.HTTPMiddleware(batchMetrics))

	// Health check endpoint (root level)
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status":  "healthy",
			"service": "batch-service",
			"version": "1.0.0",
		})
	})

	// Prometheus metrics endpoint (root level)
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// Create handlers
	storageHandler := handlers.NewStorageHandler(storageManager, logger)
	metadataHandler := handlers.NewMetadataHandler(metadataExtractor, storageManager, logger)

	// Storage Operations (internal contract - called only by Orchestrator)
	storageGroup := router.Group("/storage")
	{
		storageGroup.POST("/upload", storageHandler.UploadExtension)
		storageGroup.GET("/list", storageHandler.ListStorage)
		storageGroup.GET("/:name/metadata", storageHandler.GetExtensionMetadata)
		storageGroup.DELETE("/:name", storageHandler.DeleteExtension)
	}

	// Metadata endpoint (for extension file metadata extraction)
	router.GET("/metadata/:file", metadataHandler.GetExtensionMetadata)

	return router
}
