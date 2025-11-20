package routes

import (
	"time"

	"github.com/commandcenter1c/commandcenter/api-gateway/internal/handlers"
	"github.com/commandcenter1c/commandcenter/api-gateway/internal/middleware"
	"github.com/commandcenter1c/commandcenter/shared/auth"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

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

	// API v1 routes
	v1 := router.Group("/api/v1")
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

	return router
}
