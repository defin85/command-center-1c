package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"

	"github.com/commandcenter1c/commandcenter/installation-service/internal/config"
	"github.com/commandcenter1c/commandcenter/installation-service/internal/executor"
	"github.com/commandcenter1c/commandcenter/installation-service/internal/progress"
	"github.com/commandcenter1c/commandcenter/installation-service/internal/queue"
)

func main() {
	// Load configuration
	configPath := "config.yaml"
	if path := os.Getenv("CONFIG_PATH"); path != "" {
		configPath = path
	}

	cfg, err := config.Load(configPath)
	if err != nil {
		log.Fatal().Err(err).Str("config_path", configPath).Msg("Failed to load config")
	}

	// Setup logging
	setupLogging(cfg.Logging)

	log.Info().
		Str("version", "1.0.0-stage2").
		Str("config_path", configPath).
		Msg("Starting Installation Service")

	// Create context for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Create progress publisher
	publisher := progress.NewPublisher(&cfg.Redis)
	defer publisher.Close()

	// Check Redis connection for publisher
	if err := publisher.Ping(ctx); err != nil {
		log.Fatal().Err(err).Msg("Failed to connect to Redis for progress publisher")
	}
	log.Info().Msg("Progress publisher connected to Redis")

	// Create worker pool with publisher
	pool := executor.NewPool(&cfg.Executor, &cfg.OneC, publisher)
	pool.Start()

	// Create Redis consumer
	consumer := queue.NewConsumer(&cfg.Redis)

	// Start consumer in goroutine
	go func() {
		if err := consumer.Start(ctx, pool.TaskChannel()); err != nil && err != context.Canceled {
			log.Error().Err(err).Msg("Consumer error")
		}
	}()

	// Start health check server
	healthServer := startHealthCheckServer(cfg.Server.HealthCheckPort, consumer)

	// Process results in goroutine
	go processResults(pool.ResultChannel())

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigChan

	log.Info().Str("signal", sig.String()).Msg("Received shutdown signal, shutting down gracefully...")

	// Graceful shutdown
	cancel()

	shutdownCtx, shutdownCancel := context.WithTimeout(
		context.Background(),
		time.Duration(cfg.Server.ShutdownTimeout)*time.Second,
	)
	defer shutdownCancel()

	// Shutdown health check server
	if err := healthServer.Shutdown(shutdownCtx); err != nil {
		log.Error().Err(err).Msg("Health check server shutdown error")
	}

	// Wait for worker pool and consumer to finish
	done := make(chan struct{})
	go func() {
		pool.Stop()
		consumer.Close()
		close(done)
	}()

	select {
	case <-done:
		log.Info().Msg("Graceful shutdown completed")
	case <-shutdownCtx.Done():
		log.Warn().Msg("Shutdown timeout exceeded, forcing exit")
	}
}

// setupLogging configures zerolog for the application
func setupLogging(cfg config.LoggingConfig) {
	// Parse log level
	level, err := zerolog.ParseLevel(cfg.Level)
	if err != nil {
		level = zerolog.InfoLevel
	}
	zerolog.SetGlobalLevel(level)

	// Console output with nice formatting for development
	log.Logger = log.Output(zerolog.ConsoleWriter{
		Out:        os.Stderr,
		TimeFormat: time.RFC3339,
	})

	// TODO: Add file output with rotation (Stage 4 or later)
	// if cfg.File != "" {
	//     // Setup file logging with rotation
	// }

	log.Info().
		Str("level", level.String()).
		Msg("Logging configured")
}

// startHealthCheckServer starts HTTP server for health checks
func startHealthCheckServer(port int, consumer *queue.Consumer) *http.Server {
	mux := http.NewServeMux()

	// Health check endpoint
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()

		// Check Redis connection
		if err := consumer.HealthCheck(ctx); err != nil {
			log.Error().Err(err).Msg("Health check failed: Redis unavailable")
			w.WriteHeader(http.StatusServiceUnavailable)
			w.Write([]byte(`{"status":"unhealthy","error":"redis_unavailable"}`))
			return
		}

		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ok","service":"installation-service","version":"1.0.0-stage2"}`))
	})

	// Ready check endpoint (for Kubernetes readiness probe)
	mux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ready"}`))
	})

	server := &http.Server{
		Addr:         fmt.Sprintf(":%d", port),
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	go func() {
		log.Info().
			Int("port", port).
			Msg("Health check server started")

		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error().Err(err).Msg("Health check server error")
		}
	}()

	return server
}

// processResults processes task results from worker pool
func processResults(resultChan <-chan executor.TaskResult) {
	for result := range resultChan {
		log.Info().
			Str("task_id", result.TaskID).
			Int("database_id", result.DatabaseID).
			Str("database_name", result.DatabaseName).
			Str("status", result.Status).
			Int("duration", result.DurationSeconds).
			Str("error", result.ErrorMessage).
			Msg("Task result processed")

		// Events are already published in publisher via executeTask
		// Optional: HTTP callback to Orchestrator can be added here
		// Example:
		// if err := sendOrchestratorCallback(result); err != nil {
		//     log.Error().Err(err).Msg("Failed to send callback to orchestrator")
		// }
	}

	log.Info().Msg("Result processor stopped")
}
