package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"

	"github.com/command-center-1c/cluster-service/internal/api"
	"github.com/command-center-1c/cluster-service/internal/api/handlers"
	"github.com/command-center-1c/cluster-service/internal/config"
	"github.com/command-center-1c/cluster-service/internal/grpc"
	"github.com/command-center-1c/cluster-service/internal/monitor"
	"github.com/command-center-1c/cluster-service/internal/server"
	"github.com/command-center-1c/cluster-service/internal/service"
	"github.com/command-center-1c/cluster-service/internal/version"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

var showVersion bool

func init() {
	// Register version flag
	flag.BoolVar(&showVersion, "version", false, "Show version information and exit")
}

func main() {
	flag.Parse()

	if showVersion {
		fmt.Printf("Service: cc1c-cluster-service\n")
		fmt.Printf("Version: %s\n", version.Version)
		fmt.Printf("Commit: %s\n", version.Commit)
		fmt.Printf("Built: %s\n", version.BuildTime)
		os.Exit(0)
	}

	// Load config
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	// Initialize logger
	logger, err := initLogger(cfg.Log.Level)
	if err != nil {
		log.Fatalf("failed to initialize logger: %v", err)
	}
	defer logger.Sync()

	logger.Info("starting cluster-service",
		zap.String("service", "cc1c-cluster-service"),
		zap.String("version", version.Version),
		zap.String("commit", version.Commit),
		zap.String("buildTime", version.BuildTime),
		zap.String("grpc_gateway", cfg.GRPC.GatewayAddr),
	)

	// Initialize gRPC client
	grpcClient, err := grpc.NewClient(context.Background(), cfg.GRPC.GatewayAddr, logger)
	if err != nil {
		logger.Fatal("failed to create gRPC client", zap.Error(err))
	}
	defer grpcClient.Close()

	logger.Info("gRPC client initialized", zap.String("addr", cfg.GRPC.GatewayAddr))

	// Initialize Redis client for Pub/Sub
	var redisClient *redis.Client
	var sessionsMonitor *monitor.SessionsMonitor

	if cfg.Monitor.PubSubEnabled {
		redisAddr := fmt.Sprintf("%s:%s", cfg.Redis.Host, cfg.Redis.Port)
		redisClient = redis.NewClient(&redis.Options{
			Addr:     redisAddr,
			Password: cfg.Redis.Password,
			DB:       cfg.Redis.DB,
		})

		// Test Redis connection
		if err := redisClient.Ping(context.Background()).Err(); err != nil {
			logger.Error("failed to connect to Redis, Pub/Sub disabled",
				zap.String("addr", redisAddr),
				zap.Error(err),
			)
			redisClient = nil
		} else {
			logger.Info("Redis client initialized for Pub/Sub",
				zap.String("addr", redisAddr),
			)
		}
	} else {
		logger.Info("Redis Pub/Sub disabled by configuration")
	}

	// Service layer
	monitoringService := service.NewMonitoringService(grpcClient, logger)
	infobaseMgmtService := service.NewInfobaseManagementService(grpcClient, logger, cfg.GRPC.RASGWHTTPURL)

	// Initialize sessions monitor if Redis is available
	if redisClient != nil {
		sessionsMonitor = monitor.NewSessionsMonitor(
			infobaseMgmtService,
			redisClient,
			monitor.MonitorConfig{
				PollInterval: cfg.Monitor.SessionMonitorInterval,
			},
			logger,
		)
		logger.Info("sessions monitor initialized",
			zap.Duration("poll_interval", cfg.Monitor.SessionMonitorInterval),
		)
	}

	// Handlers
	monitoringHandler := handlers.NewMonitoringHandler(
		monitoringService,
		cfg.GRPC.RequestTimeout,
		logger,
	)
	infobaseMgmtHandler := handlers.NewInfobaseManagementHandler(
		infobaseMgmtService,
		sessionsMonitor,
		cfg.GRPC.RequestTimeout,
		logger,
	)

	// Router
	router := api.SetupRouter(monitoringHandler, infobaseMgmtHandler, logger)

	// HTTP server
	addr := fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port)
	srv := server.NewServer(
		router,
		addr,
		cfg.Server.ReadTimeout,
		cfg.Server.WriteTimeout,
		cfg.Server.ShutdownTimeout,
		logger,
	)

	// Start (blocks until shutdown)
	if err := srv.Start(); err != nil {
		logger.Fatal("server error", zap.Error(err))
	}

	// Cleanup Redis connection
	if redisClient != nil {
		redisClient.Close()
		logger.Info("Redis connection closed")
	}
}

func initLogger(level string) (*zap.Logger, error) {
	var zapConfig zap.Config

	if level == "debug" {
		zapConfig = zap.NewDevelopmentConfig()
	} else {
		zapConfig = zap.NewProductionConfig()
	}

	zapLevel, err := zap.ParseAtomicLevel(level)
	if err != nil {
		return nil, fmt.Errorf("invalid log level: %w", err)
	}
	zapConfig.Level = zapLevel

	return zapConfig.Build()
}
