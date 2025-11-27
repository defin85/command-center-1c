package routes

import (
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/api-gateway/internal/handlers"
	"github.com/commandcenter1c/commandcenter/api-gateway/internal/middleware"
	"github.com/commandcenter1c/commandcenter/shared/auth"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

// serviceUnavailableHandler returns a handler that responds with 503 Service Unavailable
func serviceUnavailableHandler(serviceName string) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(503, gin.H{
			"error": fmt.Sprintf("%s service unavailable", serviceName),
			"code":  "SERVICE_UNAVAILABLE",
		})
	}
}

// SetupRouter configures and returns the Gin router
func SetupRouter(cfg *config.Config) *gin.Engine {
	router := gin.New()

	// Отключаем автоматические редиректы trailing slash
	router.RedirectTrailingSlash = false
	router.RedirectFixedPath = false

	// Global middleware
	router.Use(gin.Recovery())
	router.Use(middleware.LoggerMiddleware())
	router.Use(middleware.CORSMiddleware())

	// Health check endpoint (no auth required)
	router.GET("/health", handlers.HealthCheck)

	// Metrics endpoint (no auth required)
	if cfg.MetricsEnabled {
		router.GET("/metrics", gin.WrapH(promhttp.Handler()))
	}

	// API v1 routes (deprecated)
	v1 := router.Group("/api/v1")

	// Add deprecation warning headers if enabled
	if cfg.V1DeprecationEnabled {
		v1.Use(middleware.DeprecationWarning(cfg.V1SunsetDate))
	}

	{
		// Public routes (no auth)
		public := v1.Group("/public")
		{
			public.GET("/status", handlers.GetStatus)
		}

		// Protected routes (auth required)
		jwtManager := auth.NewJWTManager(auth.JWTConfig{
			Secret:     cfg.JWTSecret,
			ExpireTime: cfg.JWTExpireTime,
			Issuer:     cfg.JWTIssuer,
		})

		protected := v1.Group("")
		protected.Use(auth.AuthMiddleware(jwtManager))
		protected.Use(middleware.RateLimitMiddleware(100, time.Minute)) // 100 req/min
		{
			// Operations endpoints
			operations := protected.Group("/operations")
			{
				operations.GET("", handlers.ProxyToOrchestrator)
		operations.GET("/", handlers.ProxyToOrchestrator) // Trailing slash для Django DRF
				operations.GET("/:id", handlers.ProxyToOrchestrator)
				operations.POST("/:id/cancel", handlers.ProxyToOrchestrator)
				operations.POST("/:id/callback", handlers.ProxyToOrchestrator)
			}

			// Databases endpoints
			databases := protected.Group("/databases")
			{
				// Database endpoints
				databases.GET("", handlers.ProxyToOrchestrator)
				databases.GET("/:id", handlers.ProxyToOrchestrator)
				databases.GET("/:id/health", handlers.ProxyToOrchestrator)
				databases.POST("/:id/install-extension/", handlers.ProxyToOrchestrator)
				databases.GET("/:id/extension-status/", handlers.ProxyToOrchestrator)
				databases.PATCH("/:id/extension-installation-status/", handlers.ProxyToOrchestrator)
				databases.POST("/:id/retry-installation/", handlers.ProxyToOrchestrator)
				databases.POST("/batch-install-extension/", handlers.ProxyToOrchestrator)
				databases.GET("/installation-progress/:task_id/", handlers.ProxyToOrchestrator)
			} // Cluster management (отдельный путь, маппится на /clusters в Django)
			clusters := protected.Group("/databases/clusters")
			{
				clusters.GET("", handlers.ProxyToOrchestrator)
				clusters.POST("", handlers.ProxyToOrchestrator)
				clusters.GET("/:id", handlers.ProxyToOrchestrator)
				clusters.PUT("/:id", handlers.ProxyToOrchestrator)
				clusters.PATCH("/:id", handlers.ProxyToOrchestrator)
				clusters.DELETE("/:id", handlers.ProxyToOrchestrator)
				clusters.POST("/:id/sync", handlers.ProxyToOrchestrator)
				clusters.GET("/:id/databases", handlers.ProxyToOrchestrator)
			}

			// System monitoring endpoints
			system := protected.Group("/system")
			{
				system.GET("/health", handlers.ProxyToOrchestrator)
			}

			// Extension storage endpoints
			extensions := protected.Group("/extensions")
			{
				extensions.GET("/storage/", handlers.ProxyToOrchestrator)
				extensions.POST("/upload/", handlers.ProxyToOrchestrator)
				extensions.DELETE("/storage/:filename/", handlers.ProxyToOrchestrator)
			}
		}
	}

	// API v2 routes (new version)
	setupV2Routes(router, cfg)

	return router
}

// setupV2Routes configures API v2 routes with RAS Adapter and Jaeger proxies
func setupV2Routes(router *gin.Engine, cfg *config.Config) {
	log := logger.GetLogger()

	// Initialize RAS Adapter proxy with fallback
	var rasHandler gin.HandlerFunc
	rasProxy, err := handlers.NewRASProxyHandler(cfg.RASAdapterURL)
	if err != nil {
		log.Error("Failed to initialize RAS proxy, using fallback handler", zap.Error(err))
		rasHandler = serviceUnavailableHandler("RAS Adapter")
	} else {
		rasHandler = rasProxy.Handle
	}

	// Initialize Jaeger proxy with fallback
	var jaegerHandler gin.HandlerFunc
	jaegerProxy, err := handlers.NewJaegerProxyHandler(cfg.JaegerURL)
	if err != nil {
		log.Error("Failed to initialize Jaeger proxy, using fallback handler", zap.Error(err))
		jaegerHandler = serviceUnavailableHandler("Jaeger")
	} else {
		jaegerHandler = jaegerProxy.Handle
	}

	// JWT Manager for authentication
	jwtManager := auth.NewJWTManager(auth.JWTConfig{
		Secret:     cfg.JWTSecret,
		ExpireTime: cfg.JWTExpireTime,
		Issuer:     cfg.JWTIssuer,
	})

	// V2 routes group
	v2 := router.Group("/api/v2")
	v2.Use(auth.AuthMiddleware(jwtManager))
	v2.Use(middleware.RateLimitMiddleware(100, time.Minute)) // 100 req/min
	{
		// RAS Adapter routes - Cluster management (GET for list/get operations)
		v2.GET("/list-clusters", rasHandler)
		v2.GET("/get-cluster", rasHandler)

		// RAS Adapter routes - Infobase management
		v2.GET("/list-infobases", rasHandler)
		v2.GET("/get-infobase", rasHandler)
		v2.POST("/create-infobase", rasHandler)
		v2.POST("/drop-infobase", rasHandler)

		// RAS Adapter routes - Lock/Unlock (POST for state-changing operations)
		v2.POST("/lock-infobase", rasHandler)
		v2.POST("/unlock-infobase", rasHandler)
		v2.POST("/block-sessions", rasHandler)
		v2.POST("/unblock-sessions", rasHandler)

		// RAS Adapter routes - Session management
		v2.GET("/list-sessions", rasHandler)
		v2.POST("/terminate-session", rasHandler)
		v2.POST("/terminate-sessions", rasHandler)

		// Jaeger tracing routes
		v2.Any("/tracing/*path", jaegerHandler)

		// Orchestrator routes (all other v2 paths)
		v2.Any("/operations/*path", handlers.ProxyToOrchestratorV2)
		v2.Any("/databases/*path", handlers.ProxyToOrchestratorV2)
		v2.Any("/workflows/*path", handlers.ProxyToOrchestratorV2)
		v2.Any("/system/*path", handlers.ProxyToOrchestratorV2)
	}

	log.Info("API v2 routes configured",
		zap.String("ras_adapter", cfg.RASAdapterURL),
		zap.String("jaeger", cfg.JaegerURL),
	)
}
