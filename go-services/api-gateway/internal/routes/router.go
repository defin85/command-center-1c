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
	// Convention: все routes и запросы используют trailing slash (Django source of truth)
	// Frontend interceptor автоматически добавляет trailing slash
	router.RedirectTrailingSlash = false
	router.RedirectFixedPath = false

	// Global middleware
	router.Use(gin.Recovery())
	router.Use(middleware.LoggerMiddleware())
	router.Use(middleware.CORSMiddleware(&middleware.CORSConfig{
		AllowedOrigins: cfg.CORSAllowedOrigins,
	}))

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

	// WebSocket routes (no auth middleware - handles internally)
	router.GET("/ws/workflow/:execution_id/", handlers.WebSocketWorkflowProxy)
	router.GET("/ws/service-mesh/", handlers.WebSocketServiceMeshProxy)

	// API v2 routes (v1 removed after migration - 2025-11-27)
	// SSE routes (e.g., /operations/stream/) handled via sseRoutes map in orchestrator_routes.go
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
		// RAS Adapter routes (infobase, session management, cluster operations)
		RegisterRASRoutes(v2, rasHandler)

		// Jaeger tracing routes
		v2.Any("/tracing/*path", jaegerHandler)

		// Orchestrator routes (Django backend for CRUD operations)
		// Routes are generated from OpenAPI spec + fallback wildcards
		RegisterOrchestratorRoutes(v2, handlers.ProxyToOrchestratorV2)
	}

	log.Info("API v2 routes configured",
		zap.String("ras_adapter", cfg.RASAdapterURL),
		zap.String("jaeger", cfg.JaegerURL),
	)
}
