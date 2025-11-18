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

	// Debug: Show JWT configuration (first 10 chars of secret for security)
	jwtSecretPreview := cfg.JWTSecret
	if len(jwtSecretPreview) > 10 {
		jwtSecretPreview = jwtSecretPreview[:10] + "..."
	}
	log.Info("JWT configuration loaded",
		zap.String("jwt_secret_preview", jwtSecretPreview),
		zap.String("jwt_issuer", cfg.JWTIssuer),
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

	// Debug: Show first 20 chars of generated token for debugging
	tokenPreview := serviceToken
	if len(tokenPreview) > 20 {
		tokenPreview = tokenPreview[:20] + "..."
	}
	log.Info("service token details",
		zap.String("token_preview", tokenPreview),
		zap.String("for_service", "worker"),
	)

	// Validate transport encryption key
	transportKey := []byte(cfg.CredentialsTransportKey)
	if len(transportKey) < 32 {
		log.Fatal("CREDENTIALS_TRANSPORT_KEY must be at least 32 bytes",
			zap.Int("current_length", len(transportKey)),
			zap.Int("required_length", 32),
		)
	}
	log.Info("credentials transport encryption configured",
		zap.Int("key_length", len(transportKey)),
		zap.String("algorithm", "AES-GCM-256"),
	)

	// Initialize credentials client with JWT token and transport key
	credsClient := credentials.NewClient(
		cfg.OrchestratorURL,
		serviceToken,
		transportKey, // AES-256 key for decrypting credentials payload
	)
	log.Info("credentials client initialized with encrypted transport")

	// Initialize task processor
	taskProcessor := processor.NewTaskProcessor(cfg, credsClient)
	log.Info("task processor initialized")

	// Log feature flags configuration
	featureFlags := taskProcessor.GetFeatureFlags()
	log.Info("feature flags loaded",
		zap.Bool("event_driven_enabled", featureFlags["enable_event_driven"].(bool)),
		zap.Float64("rollout_percentage", featureFlags["rollout_percentage"].(float64)),
		zap.Int("max_concurrent_events", featureFlags["max_concurrent_events"].(int)),
	)

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
