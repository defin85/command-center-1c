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

	// Public auth endpoints (no JWT required)
	// Proxy to Django Orchestrator for token generation
	router.POST("/api/token", handlers.ProxyToOrchestratorAuth)
	router.POST("/api/token/", handlers.ProxyToOrchestratorAuth)
	router.POST("/api/token/refresh", handlers.ProxyToOrchestratorAuth)
	router.POST("/api/token/refresh/", handlers.ProxyToOrchestratorAuth)

	// API v2 routes (v1 removed after migration - 2025-11-27)
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
		// RAS Adapter routes - Infobase management via /infobases/ group
		infobases := v2.Group("/infobases")
		{
			infobases.GET("/list-infobases", rasHandler)
			infobases.GET("/get-infobase", rasHandler)
			infobases.POST("/create-infobase", rasHandler)
			infobases.POST("/drop-infobase", rasHandler)
			infobases.POST("/lock-infobase", rasHandler)
			infobases.POST("/unlock-infobase", rasHandler)
			infobases.POST("/block-sessions", rasHandler)
			infobases.POST("/unblock-sessions", rasHandler)
		}

		// RAS Adapter routes - Session management via /sessions/ group
		sessions := v2.Group("/sessions")
		{
			sessions.GET("/list-sessions", rasHandler)
			sessions.POST("/terminate-session", rasHandler)
			sessions.POST("/terminate-sessions", rasHandler)
		}

		// Legacy flat routes (for backward compatibility)
		v2.GET("/list-clusters", rasHandler)
		v2.GET("/get-cluster", rasHandler)
		v2.GET("/list-infobases", rasHandler)
		v2.GET("/get-infobase", rasHandler)
		v2.POST("/create-infobase", rasHandler)
		v2.POST("/drop-infobase", rasHandler)
		v2.POST("/lock-infobase", rasHandler)
		v2.POST("/unlock-infobase", rasHandler)
		v2.POST("/block-sessions", rasHandler)
		v2.POST("/unblock-sessions", rasHandler)
		v2.GET("/list-sessions", rasHandler)
		v2.POST("/terminate-session", rasHandler)
		v2.POST("/terminate-sessions", rasHandler)

		// Jaeger tracing routes
		v2.Any("/tracing/*path", jaegerHandler)

		// Orchestrator routes (Django backend for CRUD operations)
		v2.Any("/operations/*path", handlers.ProxyToOrchestratorV2)
		v2.Any("/databases/*path", handlers.ProxyToOrchestratorV2)
		v2.Any("/clusters/*path", handlers.ProxyToOrchestratorV2)  // Cluster CRUD
		v2.Any("/workflows/*path", handlers.ProxyToOrchestratorV2)
		v2.Any("/system/*path", handlers.ProxyToOrchestratorV2)
	}

	log.Info("API v2 routes configured",
		zap.String("ras_adapter", cfg.RASAdapterURL),
		zap.String("jaeger", cfg.JaegerURL),
	)
}
