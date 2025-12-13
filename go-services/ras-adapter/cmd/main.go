package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/api/rest"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/config"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/eventhandlers"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/metrics"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/ras"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/server"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/version"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/redis/go-redis/v9"
	"github.com/ThreeDotsLabs/watermill"
	"go.uber.org/zap"
)

func main() {
	// Initialize logger
	logger, err := zap.NewProduction()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to initialize logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	logger.Info("starting RAS Adapter",
		zap.String("version", version.Version),
		zap.String("commit", version.Commit),
		zap.String("build_time", version.BuildTime))

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		logger.Fatal("failed to load config", zap.Error(err))
	}

	logger.Info("configuration loaded",
		zap.String("server_host", cfg.Server.Host),
		zap.Int("server_port", cfg.Server.Port),
		zap.String("ras_server", cfg.RAS.ServerAddr),
		zap.String("redis_host", cfg.Redis.Host),
		zap.String("redis_port", cfg.Redis.Port))

	// Initialize RAS connection pool
	rasPool, err := ras.NewPool(
		cfg.RAS.ServerAddr,
		cfg.RAS.MaxConnections,
		cfg.RAS.ConnTimeout,
		cfg.RAS.RequestTimeout,
		logger,
	)
	if err != nil {
		logger.Fatal("failed to create RAS pool", zap.Error(err))
	}
	defer rasPool.Close()

	logger.Info("RAS connection pool initialized",
		zap.String("server", cfg.RAS.ServerAddr),
		zap.Int("max_connections", cfg.RAS.MaxConnections))

	// Initialize Redis client (for Event Bus and idempotency)
	redisClient := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", cfg.Redis.Host, cfg.Redis.Port),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})
	defer redisClient.Close()

	// Test Redis connection
	if err := redisClient.Ping(context.Background()).Err(); err != nil {
		logger.Fatal("failed to connect to Redis", zap.Error(err))
	}

	logger.Info("connected to Redis",
		zap.String("addr", fmt.Sprintf("%s:%s", cfg.Redis.Host, cfg.Redis.Port)))

	// Initialize Watermill logger for event bus
	watermillLogger := watermill.NewStdLogger(false, false)

	// Initialize Event Publisher/Subscriber
	publisher, err := events.NewPublisher(redisClient, "ras-adapter", watermillLogger)
	if err != nil {
		logger.Fatal("failed to create event publisher", zap.Error(err))
	}

	subscriber, err := events.NewSubscriber(redisClient, "ras-adapter-consumer", watermillLogger)
	if err != nil {
		logger.Fatal("failed to create event subscriber", zap.Error(err))
	}

	// Initialize Services
	clusterSvc := service.NewClusterService(rasPool, logger)
	infobaseSvc := service.NewInfobaseService(rasPool, logger)
	sessionSvc := service.NewSessionService(rasPool, logger)

	logger.Info("services initialized")

	// Initialize Prometheus metrics
	rasMetrics := metrics.NewRASMetrics()
	logger.Info("prometheus metrics initialized")

	// Initialize Timeline recorder for observability
	timelineCfg := tracing.DefaultTimelineConfig("ras-adapter")
	timeline := tracing.NewRedisTimeline(redisClient, timelineCfg)
	logger.Info("timeline recorder initialized")

	// Initialize Event Handlers with metrics and timeline
	terminateHandler := eventhandlers.NewTerminateHandler(sessionSvc, publisher, redisClient, rasMetrics, timeline, logger)
	lockHandler := eventhandlers.NewLockHandler(infobaseSvc, publisher, redisClient, rasMetrics, timeline, logger)
	unlockHandler := eventhandlers.NewUnlockHandler(infobaseSvc, publisher, redisClient, rasMetrics, timeline, logger)
	blockHandler := eventhandlers.NewBlockHandler(infobaseSvc, publisher, redisClient, rasMetrics, timeline, logger)
	unblockHandler := eventhandlers.NewUnblockHandler(infobaseSvc, publisher, redisClient, rasMetrics, timeline, logger)

	// Subscribe to Redis channels (only if PubSub enabled)
	if cfg.Monitor.PubSubEnabled {
		logger.Info("subscribing to event channels")

		// Subscribe to terminate sessions command
		if err := subscriber.Subscribe(
			eventhandlers.TerminateCommandChannel,
			terminateHandler.HandleTerminateCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to terminate command channel", zap.Error(err))
		}

		// Week 2: Subscribe to lock/unlock commands
		if err := subscriber.Subscribe(
			eventhandlers.LockCommandChannel,
			lockHandler.HandleLockCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to lock command channel", zap.Error(err))
		}

		if err := subscriber.Subscribe(
			eventhandlers.UnlockCommandChannel,
			unlockHandler.HandleUnlockCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to unlock command channel", zap.Error(err))
		}

		// Subscribe to block/unblock commands (session blocking)
		if err := subscriber.Subscribe(
			eventhandlers.BlockCommandChannel,
			blockHandler.HandleBlockCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to block command channel", zap.Error(err))
		}

		if err := subscriber.Subscribe(
			eventhandlers.UnblockCommandChannel,
			unblockHandler.HandleUnblockCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to unblock command channel", zap.Error(err))
		}

		logger.Info("subscribed to event channels",
			zap.String("terminate_channel", eventhandlers.TerminateCommandChannel),
			zap.String("lock_channel", eventhandlers.LockCommandChannel),
			zap.String("unlock_channel", eventhandlers.UnlockCommandChannel),
			zap.String("block_channel", eventhandlers.BlockCommandChannel),
			zap.String("unblock_channel", eventhandlers.UnblockCommandChannel))

		// Start subscriber router in background
		go func() {
			if err := subscriber.Run(context.Background()); err != nil {
				logger.Error("subscriber router error", zap.Error(err))
			}
		}()
	} else {
		logger.Info("Redis Pub/Sub disabled, skipping event subscriptions")
	}

	// Setup REST API router
	router := rest.NewRouter(clusterSvc, infobaseSvc, sessionSvc, rasMetrics, logger)

	// Create HTTP server
	addr := fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port)
	srv := server.NewServer(
		router,
		addr,
		cfg.Server.ReadTimeout,
		cfg.Server.WriteTimeout,
		cfg.Server.ShutdownTimeout,
		logger,
	)

	// Start HTTP server in goroutine
	go func() {
		if err := srv.Start(); err != nil {
			logger.Error("HTTP server error", zap.Error(err))
		}
	}()

	logger.Info("RAS Adapter started successfully",
		zap.String("http_addr", addr),
		zap.String("ras_server", cfg.RAS.ServerAddr))

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("shutting down RAS Adapter...")

	// Graceful shutdown
	shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.Server.ShutdownTimeout)
	defer cancel()

	// Close subscriber
	if cfg.Monitor.PubSubEnabled {
		if err := subscriber.Close(); err != nil {
			logger.Error("failed to close subscriber", zap.Error(err))
		}
	}

	// Close publisher
	if err := publisher.Close(); err != nil {
		logger.Error("failed to close publisher", zap.Error(err))
	}

	// Wait for pending timeline writes to complete (with timeout)
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

	// Shutdown HTTP server
	if err := srv.Shutdown(shutdownCtx); err != nil {
		logger.Error("HTTP server shutdown error", zap.Error(err))
	}

	logger.Info("RAS Adapter shutdown completed")
}
