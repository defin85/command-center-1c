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

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/metrics"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/workflowops"
	"github.com/commandcenter1c/commandcenter/worker/internal/handlers"
	"github.com/commandcenter1c/commandcenter/worker/internal/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
	"github.com/commandcenter1c/commandcenter/worker/internal/queue"
	"github.com/commandcenter1c/commandcenter/worker/internal/rasadapter"
	"github.com/commandcenter1c/commandcenter/worker/internal/scheduler"
	"github.com/commandcenter1c/commandcenter/worker/internal/scheduler/jobs"
	"github.com/commandcenter1c/commandcenter/worker/internal/template"
	"github.com/commandcenter1c/commandcenter/worker/internal/templatesvc"
)

var (
	// These variables are set by -ldflags during build
	Version   = "dev"
	Commit    = "unknown"
	BuildTime = "unknown"
)

var showVersion bool

// orchestratorClientWrapper wraps orchestrator.Client to match jobs.DatabaseOrchestratorClient interface
type orchestratorClientWrapper struct {
	client *orchestrator.Client
}

func (w *orchestratorClientWrapper) GetDatabasesForHealthCheck(ctx context.Context) ([]jobs.OrchestratorDatabaseInfo, error) {
	databases, err := w.client.GetDatabasesForHealthCheck(ctx)
	if err != nil {
		return nil, err
	}

	result := make([]jobs.OrchestratorDatabaseInfo, len(databases))
	for i, db := range databases {
		result[i] = jobs.OrchestratorDatabaseInfo{
			ID:       db.ID,
			ODataURL: db.ODataURL,
			Name:     db.Name,
		}
	}
	return result, nil
}

func (w *orchestratorClientWrapper) SetDatabaseHealthy(ctx context.Context, databaseID string, responseTimeMs int) error {
	return w.client.SetDatabaseHealthy(ctx, databaseID, responseTimeMs)
}

func (w *orchestratorClientWrapper) SetDatabaseUnhealthy(ctx context.Context, databaseID string, errorMessage, errorCode string) error {
	return w.client.SetDatabaseUnhealthy(ctx, databaseID, errorMessage, errorCode)
}

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

	// Initialize cc1c metrics
	appMetrics := metrics.NewMetrics("cc1c")
	log.Info("cc1c metrics initialized")

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

	// Create zap logger for components
	var zapLog *zap.Logger
	if cfg.LogLevel == "debug" {
		zapLog, _ = zap.NewDevelopment()
	} else {
		zapLog, _ = zap.NewProduction()
	}
	defer zapLog.Sync()

	// Validate and decode transport encryption key (hex-encoded)
	transportKey, err := credentials.ValidateTransportKey(cfg.CredentialsTransportKey)
	if err != nil {
		log.Fatal("CREDENTIALS_TRANSPORT_KEY invalid",
			zap.Error(err),
			zap.String("hint", "must be 64+ hex characters (32+ bytes)"),
		)
	}
	log.Info("credentials transport encryption configured",
		zap.Int("key_length", len(transportKey)),
		zap.String("algorithm", "AES-GCM-256"),
	)

	// Initialize credentials fetcher (Redis Streams only; internal HTTP endpoint removed)
	streamsClient, err := credentials.NewStreamsClient(credentials.StreamsClientConfig{
		RedisClient:    redisClient,
		TransportKey:   transportKey,
		RequestTimeout: cfg.StreamsCredentialsTimeout,
		Logger:         zapLog,
	})
	if err != nil {
		log.Fatal("failed to initialize streams credentials client", zap.Error(err))
	}
	defer streamsClient.Close()
	credsClient := credentials.Fetcher(streamsClient)
	log.Info("credentials client initialized (Redis Streams)")

	// Initialize TimelineRecorder for operation tracing
	timelineCfg := tracing.DefaultTimelineConfig("worker")
	timeline := tracing.NewRedisTimeline(redisClient, timelineCfg)
	log.Info("timeline recorder initialized",
		zap.String("service", "worker"),
		zap.Duration("ttl", timelineCfg.TTL),
		zap.Int("max_entries", timelineCfg.MaxEntries),
	)

	// Shared OData service for drivers and workflows.
	odataPool := odata.NewClientPool()
	odataService := odata.NewService(odataPool)

	// Initialize template engine (Phase 4.6)
	var templateEngine *template.EngineWithFallback
	var templateClient templatesvc.TemplateClient

	if cfg.EnableGoTemplateEngine {
		log.Info("initializing Go template engine",
			zap.Duration("render_timeout", cfg.TemplateRenderTimeout),
		)

		// Create base template engine
		baseEngine := template.NewEngine(zapLog)

		// Create orchestrator client for template fetching and fallback rendering
		orchClientForTemplates, err := orchestrator.NewClientWithConfig(orchestrator.ClientConfig{
			BaseURL: cfg.OrchestratorURL,
			Token:   cfg.InternalAPIToken,
		})
		if err != nil {
			log.Warn("failed to create orchestrator client for templates, template engine disabled",
				zap.Error(err),
			)
		} else {
			// Create fallback renderer for Python Jinja2 compatibility
			fallbackRenderer := orchestrator.NewFallbackRenderer(orchClientForTemplates)

			// Create engine with fallback support
			templateEngine = template.NewEngineWithFallback(baseEngine, fallbackRenderer, zapLog)

			// Create template client adapter
			templateClient = templatesvc.NewOrchestratorTemplateClient(orchClientForTemplates)

			log.Info("template engine initialized with Python fallback support")
		}
	} else {
		log.Info("Go template engine is disabled (set ENABLE_GO_TEMPLATE_ENGINE=true to enable)")
	}

	// Initialize workflow client for execute_workflow operations
	var workflowClient workflowops.WorkflowClient
	orchClientForWorkflows, err := orchestrator.NewClientWithConfig(orchestrator.ClientConfig{
		BaseURL: cfg.OrchestratorURL,
		Token:   cfg.InternalAPIToken,
	})
	if err != nil {
		log.Warn("failed to create orchestrator client for workflows, execute_workflow disabled",
			zap.Error(err),
		)
	} else {
		workflowClient = workflowops.NewOrchestratorWorkflowClient(orchClientForWorkflows)
		log.Info("workflow client initialized for execute_workflow operations")
	}

	// Initialize task processor with Redis client for event publishing and State Machine
	processorOpts := processor.ProcessorOptions{
		TemplateEngine:  templateEngine,
		TemplateClient:  templateClient,
		WorkflowClient:  workflowClient,
		OrchestratorURL: cfg.OrchestratorURL,
		ODataService:    odataService,
		Logger:          zapLog,
		Metrics:         appMetrics,
		Timeline:        timeline,
	}
	taskProcessor := processor.NewTaskProcessorWithOptions(cfg, credsClient, redisClient, processorOpts)
	defer taskProcessor.Close() // Graceful shutdown for event subscriber
	log.Info("task processor initialized with event publishing and State Machine support",
		zap.Bool("template_engine_enabled", templateEngine != nil),
		zap.Bool("workflow_enabled", workflowClient != nil),
		zap.Bool("timeline_enabled", timeline != nil),
	)

	// Log feature flags configuration
	featureFlags := taskProcessor.GetFeatureFlags()
	log.Info("feature flags loaded",
		zap.Bool("event_driven_enabled", featureFlags["enable_event_driven"].(bool)),
		zap.Float64("rollout_percentage", featureFlags["rollout_percentage"].(float64)),
		zap.Int("max_concurrent_events", featureFlags["max_concurrent_events"].(int)),
	)

	// Initialize queue consumer (Redis Streams based)
	consumer, err := queue.NewConsumer(cfg, taskProcessor, redisClient, timeline)
	if err != nil {
		log.Fatal("failed to initialize consumer", zap.Error(err))
	}

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
			"cluster_health_cron":  schedConfig.ClusterHealthCron,
			"database_health_cron": schedConfig.DatabaseHealthCron,
			"ras_adapter_url":      schedConfig.RASAdapterURL,
		}).Info("initializing Go scheduler")

		// Reuse zapLog created above for scheduler
		{
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

			// Note: CleanupReplayedEventsJob registration moved after orchestratorClient creation
			// to use the real EventReplayClient instead of stub HTTPOrchestratorClient

			// Register batch service health check job
			batchHealthJob := jobs.NewBatchServiceHealthJob(batchClient, zapLog)
			if err := sched.RegisterJob(schedConfig.BatchHealthCron, batchHealthJob); err != nil {
				log.WithError(err).Error("failed to register batch_service_health job")
			}

			// Register cluster health check job
			rasAdapterClient, err := rasadapter.NewClientWithConfig(rasadapter.ClientConfig{
				BaseURL: schedConfig.RASAdapterURL,
			})
			if err != nil {
				log.WithError(err).Error("failed to create RAS Adapter client for cluster health")
			} else {
				rasClientAdapter := jobs.NewRASClientAdapter(rasAdapterClient)
				orchHealthClient := jobs.NewHTTPOrchestratorHealthClient(
					cfg.OrchestratorURL,
					cfg.InternalAPIToken,
					zapLog,
				)
				clusterHealthJob := jobs.NewClusterHealthJob(rasClientAdapter, orchHealthClient, zapLog)
				if err := sched.RegisterJob(schedConfig.ClusterHealthCron, clusterHealthJob); err != nil {
					log.WithError(err).Error("failed to register cluster_health job")
				}
			}

			// Register database health check job
			orchestratorClient, err := orchestrator.NewClientWithConfig(orchestrator.ClientConfig{
				BaseURL: cfg.OrchestratorURL,
				Token:   cfg.InternalAPIToken,
			})
			if err != nil {
				log.WithError(err).Error("failed to create orchestrator client for database health")
			} else {
				// Wrap orchestrator.Client to match DatabaseOrchestratorClient interface
				dbOrchestratorClient := &orchestratorClientWrapper{client: orchestratorClient}
				dbHealthClient := jobs.NewOrchestratorDatabaseHealthAdapter(dbOrchestratorClient)
				dbHealthJob := jobs.NewDatabaseHealthJob(jobs.DatabaseHealthJobConfig{
					Client:    dbHealthClient,
					Logger:    zapLog,
					BatchSize: 10,
				})
				if err := sched.RegisterJob(schedConfig.DatabaseHealthCron, dbHealthJob); err != nil {
					log.WithError(err).Error("failed to register database_health job")
				}

				// Register cleanup replayed events job (uses real EventReplayClient)
				cleanupEventsJob := jobs.NewCleanupReplayedEventsJob(
					orchestratorClient,
					schedConfig.CleanupEventsRetentionDays,
					zapLog,
				)
				if err := sched.RegisterJob(schedConfig.CleanupEventsCron, cleanupEventsJob); err != nil {
					log.WithError(err).Error("failed to register cleanup_replayed_events job")
				} else {
					log.Info("cleanup replayed events job registered",
						zap.String("cron", schedConfig.CleanupEventsCron),
						zap.Int("retention_days", schedConfig.CleanupEventsRetentionDays),
					)
				}

				// Register event replay job (if enabled)
				if schedConfig.EventReplayEnabled {
					eventReplayJob := jobs.NewEventReplayJob(
						orchestratorClient,
						redisClient,
						zapLog,
						schedConfig.EventReplayBatchSize,
					)
					if err := sched.RegisterJob(schedConfig.EventReplayCron, eventReplayJob); err != nil {
						log.WithError(err).Error("failed to register event_replay job")
					} else {
						log.Info("event replay job registered",
							zap.String("cron", schedConfig.EventReplayCron),
							zap.Int("batch_size", schedConfig.EventReplayBatchSize),
						)
					}
				} else {
					log.Info("event replay job is disabled (set ENABLE_GO_EVENT_REPLAY=true to enable)")
				}
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

	// Start cc1c metrics updater goroutine
	go func() {
		ticker := time.NewTicker(15 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				// Update stream depth (Redis Streams based consumer)
				streamDepth := consumer.GetStreamDepth(ctx)
				appMetrics.QueueDepth.Set(float64(streamDepth))

				// Update active workers (simplified: always 1 for this worker instance)
				appMetrics.ActiveWorkers.Set(1)

				// Update pending count for monitoring
				pendingCount := consumer.GetPendingCount(ctx)

				log.Debug("cc1c metrics updated",
					zap.Int("active_workers", 1),
					zap.Int64("stream_depth", streamDepth),
					zap.Int64("pending_count", pendingCount),
				)
			}
		}
	}()

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
	// Start consumer (Redis Streams)
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

	// Wait for timeline to flush pending events (FIX: timeline.Wait())
	log.Info("waiting for timeline to flush...")
	if rt, ok := timeline.(*tracing.RedisTimeline); ok {
		rt.Wait()
		log.Info("timeline flushed")
	}

	cancel() // Trigger graceful shutdown

	log.Info("worker service stopped")
}
