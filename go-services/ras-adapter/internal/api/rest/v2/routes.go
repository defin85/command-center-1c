package v2

import (
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// SetupRoutes configures all v2 API routes
func SetupRoutes(
	router *gin.RouterGroup,
	clusterSvc ClusterService,
	infobaseSvc InfobaseService,
	sessionSvc SessionService,
) {
	// Use nil logger for backward compatibility - logs will be skipped
	SetupRoutesWithLogger(router, clusterSvc, infobaseSvc, sessionSvc, nil)
}

// SetupRoutesWithLogger configures all v2 API routes with logging support
func SetupRoutesWithLogger(
	router *gin.RouterGroup,
	clusterSvc ClusterService,
	infobaseSvc InfobaseService,
	sessionSvc SessionService,
	logger *zap.Logger,
) {
	// Discovery endpoints
	router.GET("/list-clusters", ListClusters(clusterSvc))
	router.GET("/get-cluster", GetCluster(clusterSvc))

	// Infobase management endpoints
	router.GET("/list-infobases", ListInfobases(infobaseSvc))
	router.GET("/get-infobase", GetInfobase(infobaseSvc))
	router.POST("/create-infobase", CreateInfobase(infobaseSvc))
	router.POST("/drop-infobase", DropInfobase(infobaseSvc))
	router.POST("/lock-infobase", LockInfobase(infobaseSvc))
	router.POST("/unlock-infobase", UnlockInfobase(infobaseSvc))
	router.POST("/block-sessions", BlockSessions(infobaseSvc))
	router.POST("/unblock-sessions", UnblockSessions(infobaseSvc))

	// Session management endpoints (with logger for error logging)
	router.GET("/list-sessions", ListSessions(sessionSvc, logger))
	router.POST("/terminate-session", TerminateSession(sessionSvc, logger))
	router.POST("/terminate-sessions", TerminateSessions(sessionSvc, logger))
}
