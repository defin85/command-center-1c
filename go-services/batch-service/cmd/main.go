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

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"

	"github.com/command-center-1c/batch-service/internal/api"
	"github.com/command-center-1c/batch-service/internal/config"
	"github.com/command-center-1c/batch-service/internal/domain/metadata"
	"github.com/command-center-1c/batch-service/internal/domain/rollback"
	"github.com/command-center-1c/batch-service/internal/domain/session"
	"github.com/command-center-1c/batch-service/internal/domain/storage"
	"github.com/command-center-1c/batch-service/internal/infrastructure/cluster"
	"github.com/command-center-1c/batch-service/internal/infrastructure/filesystem"
	"github.com/command-center-1c/batch-service/internal/infrastructure/v8executor"
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

	backupManager := rollback.NewBackupManager(v8exec, backupStorage, logger)
	rollbackManager := rollback.NewRollbackManager(backupManager, logger)

	logger.Info("Backup system initialized",
		zap.String("backup_path", cfg.Backup.Path),
		zap.Int("retention_backups", cfg.Backup.RetentionBackups))

	// Initialize services
	extensionInstaller := service.NewExtensionInstaller(
		cfg.V8.ExePath,
		cfg.V8.DefaultTimeout,
	)
	extensionDeleter := service.NewExtensionDeleter(
		cfg.V8.ExePath,
		cfg.V8.DefaultTimeout,
	)
	extensionLister := service.NewExtensionLister(
		cfg.V8.ExePath,
		cfg.V8.DefaultTimeout,
	)
	fileValidator := service.NewFileValidator()

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

	// Setup router with all services
	router := api.SetupRouter(
		extensionInstaller,
		extensionDeleter,
		extensionLister,
		fileValidator,
		storageManager,
		metadataExtractor,
		rollbackManager,
		backupManager,
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
