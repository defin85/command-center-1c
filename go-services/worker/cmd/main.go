package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/worker/internal/pool"
	"github.com/commandcenter1c/commandcenter/worker/internal/queue"
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
	log.Info("Starting Worker Service...")

	// Create context with cancellation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Initialize queue client
	queueClient, err := queue.NewRedisQueue(ctx, cfg)
	if err != nil {
		log.Fatalf("Failed to initialize queue: %v", err)
	}
	defer queueClient.Close()

	log.Info("Connected to Redis queue")

	// Initialize worker pool
	workerPool := pool.NewWorkerPool(cfg.WorkerPoolSize, queueClient, cfg)
	log.Infof("Initialized worker pool with %d workers", cfg.WorkerPoolSize)

	// Start worker pool
	workerPool.Start(ctx)
	log.Info("Worker pool started, waiting for tasks...")

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	<-sigChan
	log.Info("Shutting down worker service...")

	// Stop worker pool gracefully
	workerPool.Stop()
	log.Info("Worker service stopped")
}
