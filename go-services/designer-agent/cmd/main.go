package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/designer-agent/internal/api/rest"
	"github.com/commandcenter1c/commandcenter/designer-agent/internal/config"
	"github.com/commandcenter1c/commandcenter/designer-agent/internal/eventhandlers"
	"github.com/commandcenter1c/commandcenter/designer-agent/internal/metrics"
	"github.com/commandcenter1c/commandcenter/designer-agent/internal/server"
	"github.com/commandcenter1c/commandcenter/designer-agent/internal/ssh"
	"github.com/commandcenter1c/commandcenter/designer-agent/internal/version"
	"github.com/commandcenter1c/commandcenter/shared/designer"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
)

func main() {
	// Initialize logger
	logger, err := zap.NewProduction()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to initialize logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	logger.Info("starting Designer Agent",
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
		zap.String("redis_addr", cfg.Redis.Addr()),
		zap.Int("ssh_max_connections", cfg.SSH.MaxConnections),
		zap.String("log_level", cfg.Log.Level))

	// Initialize Redis client
	redisClient := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Addr(),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})
	defer redisClient.Close()

	// Test Redis connection
	if err := redisClient.Ping(context.Background()).Err(); err != nil {
		logger.Fatal("failed to connect to Redis", zap.Error(err))
	}

	logger.Info("connected to Redis", zap.String("addr", cfg.Redis.Addr()))

	// Initialize SSH connection pool
	poolConfig := ssh.PoolConfig{
		MaxConnectionsPerHost: cfg.SSH.MaxConnections,
		IdleTimeout:           cfg.SSH.IdleTimeout,
		CleanupInterval:       cfg.SSH.CleanupInterval,
		DefaultConnectTimeout: cfg.SSH.ConnectTimeout,
		DefaultCommandTimeout: cfg.SSH.CommandTimeout,
		KeepAliveInterval:     cfg.SSH.KeepAliveInterval,
		KeepAliveTimeout:      cfg.SSH.KeepAliveTimeout,
	}
	sshPool := ssh.NewPool(poolConfig, logger)
	defer sshPool.Close()

	logger.Info("SSH connection pool initialized",
		zap.Int("max_connections_per_host", cfg.SSH.MaxConnections),
		zap.Duration("idle_timeout", cfg.SSH.IdleTimeout))

	// Initialize Watermill logger for event bus
	watermillLogger := watermill.NewStdLogger(false, false)

	// Initialize Event Publisher/Subscriber
	publisher, err := events.NewPublisher(redisClient, "designer-agent", watermillLogger)
	if err != nil {
		logger.Fatal("failed to create event publisher", zap.Error(err))
	}

	subscriber, err := events.NewSubscriber(redisClient, "designer-agent-consumer", watermillLogger)
	if err != nil {
		logger.Fatal("failed to create event subscriber", zap.Error(err))
	}

	logger.Info("event bus initialized")

	// Initialize Prometheus metrics (single initialization)
	designerMetrics := metrics.NewDesignerMetrics()
	logger.Info("Prometheus metrics initialized")

	// Initialize Timeline recorder for observability
	timelineCfg := tracing.DefaultTimelineConfig("designer-agent")
	timeline := tracing.NewRedisTimeline(redisClient, timelineCfg)
	logger.Info("timeline recorder initialized")

	// Initialize Event Handlers (if PubSub enabled)
	if cfg.Monitor.PubSubEnabled {
		logger.Info("Redis Pub/Sub enabled, setting up event handlers")

		// Initialize Event Handlers with metrics and timeline
		extensionHandler := eventhandlers.NewExtensionHandler(sshPool, publisher, redisClient, designerMetrics, timeline, logger)
		configHandler := eventhandlers.NewConfigHandler(sshPool, publisher, redisClient, designerMetrics, timeline, logger)
		epfHandler := eventhandlers.NewEpfHandler(sshPool, publisher, redisClient, designerMetrics, timeline, logger)

		// Subscribe to extension command channels
		if err := subscriber.Subscribe(
			designer.StreamCommandsExtensionInstall,
			extensionHandler.HandleInstallCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to extension install channel", zap.Error(err))
		}

		if err := subscriber.Subscribe(
			designer.StreamCommandsExtensionRemove,
			extensionHandler.HandleRemoveCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to extension remove channel", zap.Error(err))
		}

		// Subscribe to config command channels
		if err := subscriber.Subscribe(
			designer.StreamCommandsConfigUpdate,
			configHandler.HandleUpdateCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to config update channel", zap.Error(err))
		}

		if err := subscriber.Subscribe(
			designer.StreamCommandsConfigLoad,
			configHandler.HandleLoadCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to config load channel", zap.Error(err))
		}

		if err := subscriber.Subscribe(
			designer.StreamCommandsConfigDump,
			configHandler.HandleDumpCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to config dump channel", zap.Error(err))
		}

		// Subscribe to EPF command channel
		if err := subscriber.Subscribe(
			designer.StreamCommandsEpfExport,
			epfHandler.HandleExportCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to epf export channel", zap.Error(err))
		}

		logger.Info("subscribed to event channels",
			zap.String("extension_install", designer.StreamCommandsExtensionInstall),
			zap.String("extension_remove", designer.StreamCommandsExtensionRemove),
			zap.String("config_update", designer.StreamCommandsConfigUpdate),
			zap.String("config_load", designer.StreamCommandsConfigLoad),
			zap.String("config_dump", designer.StreamCommandsConfigDump),
			zap.String("epf_export", designer.StreamCommandsEpfExport))

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
	router := rest.NewRouter(sshPool, redisClient, designerMetrics, logger)

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

	logger.Info("Designer Agent started successfully",
		zap.String("http_addr", addr))

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("shutting down Designer Agent...")

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

	logger.Info("Designer Agent shutdown completed")
}
