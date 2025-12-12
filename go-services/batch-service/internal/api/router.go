package api

import (
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"

	"github.com/command-center-1c/batch-service/internal/api/handlers"
	"github.com/command-center-1c/batch-service/internal/domain/metadata"
	"github.com/command-center-1c/batch-service/internal/domain/rollback"
	"github.com/command-center-1c/batch-service/internal/domain/storage"
	"github.com/command-center-1c/batch-service/internal/metrics"
	"github.com/command-center-1c/batch-service/internal/service"
)

// SetupRouter configures and returns a Gin router with all routes
func SetupRouter(
	extensionInstaller *service.ExtensionInstaller,
	extensionDeleter *service.ExtensionDeleter,
	extensionLister *service.ExtensionLister,
	fileValidator *service.FileValidator,
	storageManager *storage.Manager,
	metadataExtractor *metadata.Extractor,
	rollbackManager *rollback.RollbackManager,
	backupManager *rollback.BackupManager,
	batchMetrics *metrics.BatchMetrics,
	logger *zap.Logger,
) *gin.Engine {
	router := gin.Default()

	// Add metrics middleware (skip /metrics and /health)
	router.Use(metrics.HTTPMiddleware(batchMetrics))

	// Prometheus metrics endpoint
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// Create handlers
	extensionsHandler := handlers.NewExtensionsHandler(extensionInstaller, fileValidator)
	deleteHandler := handlers.NewDeleteExtensionHandler(extensionDeleter)
	listHandler := handlers.NewListExtensionsHandler(extensionLister)

	// Storage handler
	storageHandler := handlers.NewStorageHandler(storageManager, logger)

	// Metadata handler
	metadataHandler := handlers.NewMetadataHandler(metadataExtractor, storageManager, logger)

	// Rollback handler
	rollbackHandler := handlers.NewRollbackHandler(rollbackManager, backupManager, logger)

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Extension endpoints (existing)
		extensions := v1.Group("/extensions")
		{
			extensions.POST("/install", extensionsHandler.InstallExtension)
			extensions.POST("/batch-install", extensionsHandler.BatchInstall)
			extensions.POST("/delete", deleteHandler.Delete)
			extensions.GET("/list", listHandler.List)

			// Metadata extraction endpoint
			extensions.GET("/:file/metadata", metadataHandler.GetExtensionMetadata)

			// Rollback endpoints (NEW)
			extensions.POST("/rollback", rollbackHandler.RollbackExtension)
			extensions.GET("/rollback/history", rollbackHandler.GetRollbackHistory)

			// Backup endpoints (NEW)
			backups := extensions.Group("/backups")
			{
				backups.POST("/create", rollbackHandler.CreateManualBackup)
				backups.GET("/:database_id", rollbackHandler.ListBackupsForDatabase)
				backups.GET("/:database_id/latest", rollbackHandler.GetLatestBackup)
				backups.DELETE("/:database_id/:backup_id", rollbackHandler.DeleteBackup)
			}

			// Storage endpoints
			storage := extensions.Group("/storage")
			{
				storage.POST("/upload", storageHandler.UploadExtension)
				storage.GET("", storageHandler.ListStorage)
				storage.GET("/:name", storageHandler.GetExtensionMetadata)
				storage.DELETE("/:name", storageHandler.DeleteExtension)
			}
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
