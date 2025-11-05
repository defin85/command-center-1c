package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/worker/internal/pool"
	"github.com/commandcenter1c/commandcenter/worker/internal/queue"
	"go.uber.org/zap"
)

var (
	// These variables are set by -ldflags during build
	Version   = "dev"
	Commit    = "unknown"
	BuildTime = "unknown"
)

var showVersion bool

func init() {
	// Register version flag
	flag.BoolVar(&showVersion, "version", false, "Show version information and exit")
}

func main() {
	flag.Parse()

	if showVersion {
		fmt.Printf("Service: cc1c-worker\n")
		fmt.Printf("Version: %s\n", Version)
		fmt.Printf("Commit: %s\n", Commit)
		fmt.Printf("Built: %s\n", BuildTime)
		os.Exit(0)
	}

	// Load configuration
	cfg := config.LoadFromEnv()

	// Initialize logger
	logger.Init(logger.Config{
		Level:  cfg.LogLevel,
		Format: cfg.LogFormat,
	})

	log := logger.GetLogger()
	log.Info("starting Worker Service",
		zap.String("service", "cc1c-worker"),
		zap.String("version", Version),
		zap.String("commit", Commit),
		zap.String("buildTime", BuildTime),
	)

	// Create context with cancellation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Initialize queue client
	queueClient, err := queue.NewRedisQueue(ctx, cfg)
	if err != nil {
		log.Fatal("failed to initialize queue", zap.Error(err))
	}
	defer queueClient.Close()

	log.Info("connected to Redis queue")

	// Initialize worker pool
	workerPool := pool.NewWorkerPool(cfg.WorkerPoolSize, queueClient, cfg)
	log.Info("initialized worker pool",
		zap.Int("poolSize", cfg.WorkerPoolSize),
	)

	// Start worker pool
	workerPool.Start(ctx)
	log.Info("worker pool started, waiting for tasks")

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	<-sigChan
	log.Info("shutting down worker service")

	// Stop worker pool gracefully
	workerPool.Stop()
	log.Info("worker service stopped")
}
