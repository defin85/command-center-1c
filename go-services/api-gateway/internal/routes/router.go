package routes

import (
	"github.com/commandcenter1c/commandcenter/api-gateway/internal/handlers"
	"github.com/commandcenter1c/commandcenter/api-gateway/internal/middleware"
	"github.com/commandcenter1c/commandcenter/shared/auth"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"time"
)

// SetupRouter configures and returns the Gin router
func SetupRouter(cfg *config.Config) *gin.Engine {
	router := gin.New()

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
				operations.GET("", handlers.ListOperations)
				operations.POST("", handlers.CreateOperation)
				operations.GET("/:id", handlers.GetOperation)
				operations.DELETE("/:id", handlers.CancelOperation)
			}

			// Databases endpoints
			databases := protected.Group("/databases")
			{
				databases.GET("", handlers.ListDatabases)
				databases.GET("/:id", handlers.GetDatabase)
				databases.GET("/:id/health", handlers.CheckDatabaseHealth)
			}
		}
	}

	return router
}
