package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/auth"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/worker/internal/credentials"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
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
		zap.String("worker_id", cfg.WorkerID),
	)

	// Create context with cancellation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Generate JWT service token for Worker
	jwtManager := auth.NewJWTManager(auth.JWTConfig{
		Secret:     cfg.JWTSecret,
		ExpireTime: 24 * time.Hour, // Not used for service tokens
		Issuer:     "commandcenter",
	})

	serviceToken, err := jwtManager.GenerateServiceToken("worker", 24*time.Hour)
	if err != nil {
		log.Fatal("failed to generate service token", zap.Error(err))
	}
	log.Info("service JWT token generated", zap.Duration("ttl", 24*time.Hour))

	// Initialize credentials client with JWT token
	credsClient := credentials.NewClient(
		cfg.OrchestratorURL,
		serviceToken,
	)
	log.Info("credentials client initialized")

	// Initialize task processor
	taskProcessor := processor.NewTaskProcessor(cfg, credsClient)
	log.Info("task processor initialized")

	// Initialize queue consumer
	consumer, err := queue.NewConsumer(cfg, taskProcessor)
	if err != nil {
		log.Fatal("failed to initialize consumer", zap.Error(err))
	}
	defer consumer.Close()

	log.Info("connected to Redis queue")

	// Start consumer (blocking)
	go func() {
		if err := consumer.Start(ctx); err != nil && err != context.Canceled {
			log.Error("consumer error", zap.Error(err))
		}
	}()

	log.Info("worker started, waiting for tasks")

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	<-sigChan
	log.Info("shutting down worker service")

	cancel() // Trigger graceful shutdown

	log.Info("worker service stopped")
}
