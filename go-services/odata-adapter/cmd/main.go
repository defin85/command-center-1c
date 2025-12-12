package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/commandcenter1c/commandcenter/odata-adapter/internal/api/rest"
	"github.com/commandcenter1c/commandcenter/odata-adapter/internal/config"
	"github.com/commandcenter1c/commandcenter/odata-adapter/internal/eventhandlers"
	"github.com/commandcenter1c/commandcenter/odata-adapter/internal/odata"
	"github.com/commandcenter1c/commandcenter/odata-adapter/internal/server"
	"github.com/commandcenter1c/commandcenter/odata-adapter/internal/version"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/redis/go-redis/v9"
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

	logger.Info("starting OData Adapter",
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
		zap.String("redis_host", cfg.Redis.Host),
		zap.String("redis_port", cfg.Redis.Port),
		zap.Int("odata_max_batch_size", cfg.OData.MaxBatchSize),
		zap.Duration("odata_max_batch_timeout", cfg.OData.MaxBatchTimeout))

	// Initialize Redis client
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
	publisher, err := events.NewPublisher(redisClient, "odata-adapter", watermillLogger)
	if err != nil {
		logger.Fatal("failed to create event publisher", zap.Error(err))
	}

	subscriber, err := events.NewSubscriber(redisClient, "odata-adapter-consumer", watermillLogger)
	if err != nil {
		logger.Fatal("failed to create event subscriber", zap.Error(err))
	}

	logger.Info("event bus initialized")

	// Initialize OData connection pool
	odataPool := odata.NewPool(10, cfg.OData.DefaultTimeout)
	defer odataPool.Close()

	// Initialize OData client
	odataClient := odata.NewClient(odata.ClientConfig{
		Pool:       odataPool,
		MaxRetries: 3,
		Logger:     logger,
	})

	logger.Info("OData client initialized")

	// Initialize Event Handlers (if PubSub enabled)
	if cfg.Monitor.PubSubEnabled {
		logger.Info("Redis Pub/Sub enabled, setting up event handlers")

		// Initialize Event Handlers
		queryHandler := eventhandlers.NewQueryHandler(odataClient, publisher, redisClient, logger)
		createHandler := eventhandlers.NewCreateHandler(odataClient, publisher, redisClient, logger)
		updateHandler := eventhandlers.NewUpdateHandler(odataClient, publisher, redisClient, logger)
		deleteHandler := eventhandlers.NewDeleteHandler(odataClient, publisher, redisClient, logger)
		batchHandler := eventhandlers.NewBatchHandler(odataClient, publisher, redisClient, logger)

		// Subscribe to command channels
		if err := subscriber.Subscribe(
			eventhandlers.QueryCommandChannel,
			queryHandler.HandleQueryCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to query command channel", zap.Error(err))
		}

		if err := subscriber.Subscribe(
			eventhandlers.CreateCommandChannel,
			createHandler.HandleCreateCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to create command channel", zap.Error(err))
		}

		if err := subscriber.Subscribe(
			eventhandlers.UpdateCommandChannel,
			updateHandler.HandleUpdateCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to update command channel", zap.Error(err))
		}

		if err := subscriber.Subscribe(
			eventhandlers.DeleteCommandChannel,
			deleteHandler.HandleDeleteCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to delete command channel", zap.Error(err))
		}

		if err := subscriber.Subscribe(
			eventhandlers.BatchCommandChannel,
			batchHandler.HandleBatchCommand,
		); err != nil {
			logger.Fatal("failed to subscribe to batch command channel", zap.Error(err))
		}

		logger.Info("subscribed to event channels",
			zap.String("query_channel", eventhandlers.QueryCommandChannel),
			zap.String("create_channel", eventhandlers.CreateCommandChannel),
			zap.String("update_channel", eventhandlers.UpdateCommandChannel),
			zap.String("delete_channel", eventhandlers.DeleteCommandChannel),
			zap.String("batch_channel", eventhandlers.BatchCommandChannel))

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
	router := rest.NewRouter(redisClient, logger)

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

	logger.Info("OData Adapter started successfully",
		zap.String("http_addr", addr))

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("shutting down OData Adapter...")

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

	// Shutdown HTTP server
	if err := srv.Shutdown(shutdownCtx); err != nil {
		logger.Error("HTTP server shutdown error", zap.Error(err))
	}

	logger.Info("OData Adapter shutdown completed")
}
