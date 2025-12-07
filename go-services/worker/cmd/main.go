package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/auth"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/worker/internal/credentials"
	"github.com/commandcenter1c/commandcenter/worker/internal/handlers"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
	"github.com/commandcenter1c/commandcenter/worker/internal/queue"
	"github.com/commandcenter1c/commandcenter/worker/internal/scheduler"
	"github.com/commandcenter1c/commandcenter/worker/internal/scheduler/jobs"
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

	// Initialize Redis client (shared between processor and consumer)
	redisClient := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})

	// Test Redis connection
	if err := redisClient.Ping(ctx).Err(); err != nil {
		log.Fatal("failed to connect to Redis", zap.Error(err))
	}
	log.Info("connected to Redis", zap.String("addr", cfg.RedisHost+":"+cfg.RedisPort))

	// Initialize task processor with Redis client for event publishing and State Machine
	taskProcessor := processor.NewTaskProcessor(cfg, credsClient, redisClient)
	defer taskProcessor.Close() // Graceful shutdown for event subscriber
	log.Info("task processor initialized with event publishing and State Machine support")

	// Log feature flags configuration
	featureFlags := taskProcessor.GetFeatureFlags()
	log.Info("feature flags loaded",
		zap.Bool("event_driven_enabled", featureFlags["enable_event_driven"].(bool)),
		zap.Float64("rollout_percentage", featureFlags["rollout_percentage"].(float64)),
		zap.Int("max_concurrent_events", featureFlags["max_concurrent_events"].(int)),
	)

	// Initialize queue consumer with shared Redis client
	consumer, err := queue.NewConsumer(cfg, taskProcessor, redisClient)
	if err != nil {
		log.Fatal("failed to initialize consumer", zap.Error(err))
	}
	defer consumer.Close()

	log.Info("connected to Redis queue")

	// Initialize and start scheduler (if enabled via feature flag)
	var sched *scheduler.Scheduler
	schedConfig := scheduler.LoadConfigFromEnv()

	if schedConfig.Enabled {
		log.WithFields(map[string]interface{}{
			"enabled":              schedConfig.Enabled,
			"cleanup_history_cron": schedConfig.CleanupHistoryCron,
			"cleanup_events_cron":  schedConfig.CleanupEventsCron,
			"batch_health_cron":    schedConfig.BatchHealthCron,
		}).Info("initializing Go scheduler")

		// Create zap logger for scheduler (scheduler uses zap internally)
		var zapLog *zap.Logger
		var zapErr error
		if cfg.LogLevel == "debug" {
			zapLog, zapErr = zap.NewDevelopment()
		} else {
			zapLog, zapErr = zap.NewProduction()
		}
		if zapErr != nil {
			log.WithError(zapErr).Error("failed to create zap logger for scheduler")
		} else {
			defer zapLog.Sync()

			// Create scheduler instance
			sched = scheduler.NewWithConfig(redisClient, schedConfig, cfg.WorkerID, zapLog)

			// Create orchestrator client for cleanup jobs
			orchClient := jobs.NewHTTPOrchestratorClient(cfg.OrchestratorURL, zapLog)

			// Create batch-service client for health checks
			batchClient := jobs.NewHTTPBatchServiceClient(cfg.BatchServiceURL, zapLog)

			// Register cleanup jobs
			cleanupHistoryJob := jobs.NewCleanupStatusHistoryJob(
				orchClient,
				schedConfig.CleanupHistoryRetentionDays,
				zapLog,
			)
			if err := sched.RegisterJob(schedConfig.CleanupHistoryCron, cleanupHistoryJob); err != nil {
				log.WithError(err).Error("failed to register cleanup_status_history job")
			}

			cleanupEventsJob := jobs.NewCleanupReplayedEventsJob(
				orchClient,
				schedConfig.CleanupEventsRetentionDays,
				zapLog,
			)
			if err := sched.RegisterJob(schedConfig.CleanupEventsCron, cleanupEventsJob); err != nil {
				log.WithError(err).Error("failed to register cleanup_replayed_events job")
			}

			// Register batch service health check job
			batchHealthJob := jobs.NewBatchServiceHealthJob(batchClient, zapLog)
			if err := sched.RegisterJob(schedConfig.BatchHealthCron, batchHealthJob); err != nil {
				log.WithError(err).Error("failed to register batch_service_health job")
			}

			// Start scheduler
			if err := sched.Start(); err != nil {
				log.WithError(err).Error("failed to start scheduler")
			} else {
				log.WithField("registered_jobs", sched.GetRegisteredJobs()).Info("scheduler started successfully")
			}
		}
	} else {
		log.Info("Go scheduler is disabled (set ENABLE_GO_SCHEDULER=true to enable)")
	}

	// Start Prometheus metrics and health endpoints
	go func() {
		metricsPort := ":9091"
		mux := http.NewServeMux()
		mux.Handle("/metrics", promhttp.Handler())

		// Health endpoint with Redis check (with timeout to prevent hanging)
		mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
			// Create context with 5 second timeout to prevent hanging
			ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
			defer cancel()

			// Check Redis connectivity
			if err := redisClient.Ping(ctx).Err(); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusServiceUnavailable)
				w.Write([]byte(`{"status":"unhealthy","redis":"disconnected","error":"` + err.Error() + `"}`))
				return
			}
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"status":"healthy","redis":"connected","service":"cc1c-worker"}`))
		})

		// Rollout stats endpoint for Event-Driven rollout monitoring
		rolloutHandler := handlers.NewRolloutStatsHandler(taskProcessor.GetFeatureFlags)
		mux.Handle("/rollout-stats", rolloutHandler)

		log.Info("metrics endpoint started", zap.String("port", metricsPort))
		if err := http.ListenAndServe(metricsPort, mux); err != nil {
			log.Error("metrics endpoint failed", zap.Error(err))
		}
	}()
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

	// Stop scheduler gracefully (if running)
	if sched != nil {
		log.Info("stopping scheduler...")
		if err := sched.Stop(); err != nil {
			log.Error("error stopping scheduler", zap.Error(err))
		}
	}

	cancel() // Trigger graceful shutdown

	log.Info("worker service stopped")
}
