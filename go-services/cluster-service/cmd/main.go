package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/command-center-1c/cluster-service/internal/api"
	"github.com/command-center-1c/cluster-service/internal/api/handlers"
	"github.com/command-center-1c/cluster-service/internal/config"
	"github.com/command-center-1c/cluster-service/internal/eventhandlers"
	"github.com/command-center-1c/cluster-service/internal/grpc"
	"github.com/command-center-1c/cluster-service/internal/monitor"
	"github.com/command-center-1c/cluster-service/internal/server"
	"github.com/command-center-1c/cluster-service/internal/service"
	"github.com/command-center-1c/cluster-service/internal/version"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/commandcenter1c/commandcenter/shared/events"
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

	// Service layer (must be initialized before event handlers)
	monitoringService := service.NewMonitoringService(grpcClient, logger)
	infobaseMgmtService := service.NewInfobaseManagementService(grpcClient, logger, cfg.GRPC.RASGWHTTPURL)

	// Initialize Redis client for Event Bus and Pub/Sub
	var redisClient *redis.Client
	var sessionsMonitor *monitor.SessionsMonitor
	var eventPublisher *events.Publisher
	var eventSubscriber *events.Subscriber

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

		// Initialize Watermill logger
		watermillLogger := watermill.NewStdLogger(false, false)

		// Initialize Event Publisher
		eventPublisher, err = events.NewPublisher(redisClient, "cluster-service", watermillLogger)
		if err != nil {
			logger.Error("failed to create event publisher",
				zap.Error(err),
			)
		} else {
			logger.Info("event publisher initialized")
		}

		// Initialize Event Subscriber
		eventSubscriber, err = events.NewSubscriber(redisClient, "cluster-service-consumer", watermillLogger)
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

		// Create handlers
		lockHandler := eventhandlers.NewLockHandler(infobaseMgmtService, eventPublisher, logger)
		terminateHandler := eventhandlers.NewTerminateHandler(infobaseMgmtService, eventPublisher, logger)
		unlockHandler := eventhandlers.NewUnlockHandler(infobaseMgmtService, eventPublisher, logger)

		// Subscribe to command channels
		if err := eventSubscriber.Subscribe(eventhandlers.LockCommandChannel, lockHandler.HandleLockCommand); err != nil {
			logger.Error("failed to subscribe to lock commands",
				zap.String("channel", eventhandlers.LockCommandChannel),
				zap.Error(err))
		} else {
			logger.Info("subscribed to lock commands",
				zap.String("channel", eventhandlers.LockCommandChannel))
		}

		if err := eventSubscriber.Subscribe(eventhandlers.TerminateCommandChannel, terminateHandler.HandleTerminateCommand); err != nil {
			logger.Error("failed to subscribe to terminate commands",
				zap.String("channel", eventhandlers.TerminateCommandChannel),
				zap.Error(err))
		} else {
			logger.Info("subscribed to terminate commands",
				zap.String("channel", eventhandlers.TerminateCommandChannel))
		}

		if err := eventSubscriber.Subscribe(eventhandlers.UnlockCommandChannel, unlockHandler.HandleUnlockCommand); err != nil {
			logger.Error("failed to subscribe to unlock commands",
				zap.String("channel", eventhandlers.UnlockCommandChannel),
				zap.Error(err))
		} else {
			logger.Info("subscribed to unlock commands",
				zap.String("channel", eventhandlers.UnlockCommandChannel))
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

	// Initialize sessions monitor if Redis and PubSub are enabled
	if redisClient != nil && cfg.Monitor.PubSubEnabled {
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

	// Start HTTP server in background
	go func() {
		logger.Info("starting HTTP server", zap.String("addr", addr))
		if err := srv.Start(); err != nil {
			logger.Fatal("server error", zap.Error(err))
		}
	}()

	// Wait for interrupt signal for graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	<-sigChan

	logger.Info("shutdown signal received, starting graceful shutdown")

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

	logger.Info("graceful shutdown completed")
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
