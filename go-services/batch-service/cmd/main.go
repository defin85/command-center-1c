package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"

	"github.com/command-center-1c/batch-service/internal/api"
	"github.com/command-center-1c/batch-service/internal/config"
	"github.com/command-center-1c/batch-service/internal/domain/metadata"
	"github.com/command-center-1c/batch-service/internal/domain/rollback"
	"github.com/command-center-1c/batch-service/internal/domain/session"
	"github.com/command-center-1c/batch-service/internal/domain/storage"
	"github.com/command-center-1c/batch-service/internal/eventhandlers"
	"github.com/command-center-1c/batch-service/internal/infrastructure/cluster"
	"github.com/command-center-1c/batch-service/internal/infrastructure/filesystem"
	"github.com/command-center-1c/batch-service/internal/infrastructure/v8executor"
	"github.com/command-center-1c/batch-service/internal/metrics"
	"github.com/command-center-1c/batch-service/internal/service"
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
		fmt.Printf("Service: cc1c-batch-service\n")
		fmt.Printf("Version: %s\n", Version)
		fmt.Printf("Commit: %s\n", Commit)
		fmt.Printf("Built: %s\n", BuildTime)
		os.Exit(0)
	}

	// Initialize logger
	logger := initLogger()
	defer logger.Sync()

	// Load configuration
	cfg := config.Load()

	logger.Info("Starting batch-service",
		zap.String("service", "cc1c-batch-service"),
		zap.String("version", Version),
		zap.String("commit", Commit),
		zap.String("build_time", BuildTime))
	logger.Info("Configuration loaded",
		zap.String("server_addr", fmt.Sprintf("%s:%s", cfg.Server.Host, cfg.Server.Port)),
		zap.String("grpc_gateway", cfg.GRPC.GatewayAddr),
		zap.String("v8_exe", cfg.V8.ExePath),
		zap.String("storage_path", cfg.Storage.Path),
		zap.String("backup_path", cfg.Backup.Path),
		zap.String("cluster_service_url", cfg.ClusterServiceURL),
		zap.Duration("cluster_request_timeout", cfg.ClusterRequestTimeout),
		zap.Int("retention_versions", cfg.Storage.RetentionVersions),
		zap.Int("retention_backups", cfg.Backup.RetentionBackups))

	// Initialize cluster client for session management with configurable timeout
	clusterClient := cluster.NewClusterClient(
		cfg.ClusterServiceURL,
		cfg.ClusterRequestTimeout,
		logger,
	)

	logger.Info("cluster client initialized",
		zap.String("url", cfg.ClusterServiceURL),
		zap.Duration("timeout", cfg.ClusterRequestTimeout))

	// Health check cluster-service (non-blocking)
	if err := clusterClient.HealthCheck(); err != nil {
		logger.Warn("cluster-service not available at startup",
			zap.String("url", cfg.ClusterServiceURL),
			zap.Error(err))
		logger.Info("session termination features will be unavailable until cluster-service is ready")
	} else {
		logger.Info("cluster-service health check passed",
			zap.String("url", cfg.ClusterServiceURL))
	}

	// Initialize session manager
	_ = session.NewSessionManager(clusterClient, logger)

	// Initialize backup system
	backupStorage := filesystem.NewBackupStorage(cfg.Backup.Path, logger)

	// Initialize v8executor for backup operations
	v8exec := v8executor.NewV8Executor(
		cfg.V8.ExePath,
		cfg.V8.DefaultTimeout,
	)

	// NOTE: backupManager and rollbackManager are available if needed for future event handlers
	_ = rollback.NewBackupManager(v8exec, backupStorage, logger)

	logger.Info("Backup system initialized",
		zap.String("backup_path", cfg.Backup.Path),
		zap.Int("retention_backups", cfg.Backup.RetentionBackups))

	// Initialize services for event handlers
	// NOTE: extensionInstaller is used by InstallHandler for Redis Streams events
	extensionInstaller := service.NewExtensionInstaller(
		cfg.V8.ExePath,
		cfg.V8.DefaultTimeout,
	)
	// NOTE: extensionDeleter and extensionLister are available for future event handlers
	_ = service.NewExtensionDeleter(
		cfg.V8.ExePath,
		cfg.V8.DefaultTimeout,
	)
	_ = service.NewExtensionLister(
		cfg.V8.ExePath,
		cfg.V8.DefaultTimeout,
	)

	// Initialize storage manager
	storageManager := storage.NewManager(
		cfg.Storage.Path,
		cfg.Storage.RetentionVersions,
		logger,
	)

	logger.Info("Storage manager initialized",
		zap.String("path", cfg.Storage.Path),
		zap.Int("retention", cfg.Storage.RetentionVersions))

	// Initialize metadata extractor (reuse v8exec from backup system)
	metadataParser := metadata.NewParser(logger)
	metadataExtractor := metadata.NewExtractor(v8exec, metadataParser, logger)

	logger.Info("Metadata extractor initialized",
		zap.String("v8_exe", cfg.V8.ExePath),
		zap.Duration("timeout", cfg.V8.DefaultTimeout))

	// Initialize Prometheus metrics
	batchMetrics := metrics.NewBatchMetrics()
	logger.Info("Prometheus metrics initialized")

	// Initialize Timeline recorder for observability (will be set after Redis connection)
	var timeline tracing.TimelineRecorder

	// Initialize Redis client for Event Bus
	var redisClient *redis.Client
	var eventPublisher *events.Publisher
	var eventSubscriber *events.Subscriber

	// Feature toggle for Redis Pub/Sub event handlers
	pubSubEnabled := cfg.Redis.PubSubEnabled
	logger.Info("Redis Pub/Sub configuration",
		zap.Bool("pubsub_enabled", pubSubEnabled),
		zap.String("env_var", "REDIS_PUBSUB_ENABLED"))

	if !pubSubEnabled {
		logger.Info("Redis Pub/Sub disabled by feature toggle (REDIS_PUBSUB_ENABLED=false)")
	} else {
		redisAddr := fmt.Sprintf("%s:%s", cfg.Redis.Host, cfg.Redis.Port)
		redisClient = redis.NewClient(&redis.Options{
			Addr:     redisAddr,
			Password: cfg.Redis.Password,
			DB:       cfg.Redis.DB,
		})

		// Test Redis connection
		ctx := context.Background()
		if err := redisClient.Ping(ctx).Err(); err != nil {
			logger.Error("failed to connect to Redis",
				zap.String("addr", redisAddr),
				zap.Error(err),
			)
			// Continue without event bus (graceful degradation)
		} else {
			logger.Info("Redis client initialized",
				zap.String("addr", redisAddr),
			)

			// Initialize Timeline recorder
			timelineCfg := tracing.DefaultTimelineConfig("batch-service")
			timeline = tracing.NewRedisTimeline(redisClient, timelineCfg)
			logger.Info("timeline recorder initialized")

			// Initialize Watermill logger
			watermillLogger := watermill.NewStdLogger(false, false)

			// Initialize Event Publisher
			eventPublisher, err = events.NewPublisher(redisClient, "batch-service", watermillLogger)
			if err != nil {
				logger.Error("failed to create event publisher",
					zap.Error(err),
				)
			} else {
				logger.Info("event publisher initialized")
			}

			// Initialize Event Subscriber
			eventSubscriber, err = events.NewSubscriber(redisClient, "batch-service-consumer", watermillLogger)
			if err != nil {
				logger.Error("failed to create event subscriber",
					zap.Error(err),
				)
			} else {
				logger.Info("event subscriber initialized")
			}
		}

		// Register Event Handlers (if event system is available)
		if eventPublisher != nil && eventSubscriber != nil {
			logger.Info("registering event handlers")

			// Create handlers (pass redisClient for idempotency checks, batchMetrics for metrics recording, and timeline for observability)
			installHandler := eventhandlers.NewInstallHandler(extensionInstaller, eventPublisher, redisClient, batchMetrics, timeline, logger)

			// Subscribe to command channels
			if err := eventSubscriber.Subscribe(eventhandlers.InstallCommandChannel, installHandler.HandleInstallCommand); err != nil {
				logger.Error("failed to subscribe to install commands",
					zap.String("channel", eventhandlers.InstallCommandChannel),
					zap.Error(err))
			} else {
				logger.Info("subscribed to install commands",
					zap.String("channel", eventhandlers.InstallCommandChannel))
			}

			// Start event subscriber in background
			go func() {
				logger.Info("starting event subscriber")
				if err := eventSubscriber.Run(ctx); err != nil {
					logger.Error("event subscriber error", zap.Error(err))
				}
			}()
		} else {
			logger.Warn("event system not available, event handlers disabled")
		}
	}

	// Setup router with storage and metadata services
	// NOTE: Extension operations (install, delete, rollback) are handled via Redis Streams
	router := api.SetupRouter(
		storageManager,
		metadataExtractor,
		batchMetrics,
		logger,
	)

	// Create HTTP server
	server := &http.Server{
		Addr:         fmt.Sprintf("%s:%s", cfg.Server.Host, cfg.Server.Port),
		Handler:      router,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
	}

	// Start server in a goroutine
	go func() {
		logger.Info("Server listening", zap.String("addr", server.Addr))
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("Failed to start server", zap.Error(err))
		}
	}()

	// Wait for interrupt signal to gracefully shutdown the server
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("Shutting down server...")

	// Graceful shutdown with 5 second timeout
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		logger.Error("Server forced to shutdown", zap.Error(err))
		os.Exit(1)
	}

	// Wait for pending timeline writes to complete (with timeout)
	if timeline != nil {
		if rt, ok := timeline.(*tracing.RedisTimeline); ok {
			// Wait with timeout to avoid blocking forever
			waitCtx, waitCancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer waitCancel()

			done := make(chan struct{})
			go func() {
				rt.Wait()
				close(done)
			}()

			select {
			case <-done:
				logger.Info("timeline writes completed")
			case <-waitCtx.Done():
				logger.Warn("timeline writes timeout, some events may be lost")
			}
		}
	}

	// Close event subscriber
	if eventSubscriber != nil {
		logger.Info("closing event subscriber")
		if err := eventSubscriber.Close(); err != nil {
			logger.Error("failed to close event subscriber", zap.Error(err))
		} else {
			logger.Info("event subscriber closed")
		}
	}

	// Close event publisher
	if eventPublisher != nil {
		logger.Info("closing event publisher")
		if err := eventPublisher.Close(); err != nil {
			logger.Error("failed to close event publisher", zap.Error(err))
		} else {
			logger.Info("event publisher closed")
		}
	}

	// Close Redis connection
	if redisClient != nil {
		logger.Info("closing Redis connection")
		if err := redisClient.Close(); err != nil {
			logger.Error("failed to close Redis connection", zap.Error(err))
		} else {
			logger.Info("Redis connection closed")
		}
	}

	logger.Info("Server exited gracefully")
}

// initLogger создает и настраивает zap logger
func initLogger() *zap.Logger {
	// Настройка уровня логирования из env (по умолчанию INFO)
	logLevel := os.Getenv("LOG_LEVEL")
	level := zapcore.InfoLevel
	if logLevel != "" {
		if err := level.UnmarshalText([]byte(logLevel)); err != nil {
			log.Printf("Invalid LOG_LEVEL '%s', using INFO", logLevel)
		}
	}

	// Конфигурация logger
	config := zap.Config{
		Level:            zap.NewAtomicLevelAt(level),
		Encoding:         "json",
		OutputPaths:      []string{"stdout"},
		ErrorOutputPaths: []string{"stderr"},
		EncoderConfig: zapcore.EncoderConfig{
			TimeKey:        "timestamp",
			LevelKey:       "level",
			NameKey:        "logger",
			CallerKey:      "caller",
			MessageKey:     "message",
			StacktraceKey:  "stacktrace",
			LineEnding:     zapcore.DefaultLineEnding,
			EncodeLevel:    zapcore.LowercaseLevelEncoder,
			EncodeTime:     zapcore.ISO8601TimeEncoder,
			EncodeDuration: zapcore.SecondsDurationEncoder,
			EncodeCaller:   zapcore.ShortCallerEncoder,
		},
	}

	logger, err := config.Build()
	if err != nil {
		log.Fatalf("Failed to initialize logger: %v", err)
	}

	return logger
}
