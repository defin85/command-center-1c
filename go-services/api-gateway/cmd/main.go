package main

import (
	"fmt"

	"github.com/commandcenter1c/commandcenter/api-gateway/internal/routes"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/gin-gonic/gin"
)

func main() {
	// Load configuration
	cfg := config.LoadFromEnv()

	// Initialize logger
	logger.Init(logger.Config{
		Level:  cfg.LogLevel,
		Format: cfg.LogFormat,
	})

	log := logger.GetLogger()
	log.Info("Starting API Gateway...")

	// Set Gin mode
	if cfg.LogLevel == "debug" {
		gin.SetMode(gin.DebugMode)
	} else {
		gin.SetMode(gin.ReleaseMode)
	}

	// Setup router
	router := routes.SetupRouter(cfg)

	// Start server
	addr := fmt.Sprintf("%s:%s", cfg.ServerHost, cfg.ServerPort)
	log.Infof("API Gateway listening on %s", addr)

	if err := router.Run(addr); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
