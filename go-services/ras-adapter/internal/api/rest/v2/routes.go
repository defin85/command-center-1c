package v2

import (
	"github.com/gin-gonic/gin"
)

// SetupRoutes configures all v2 API routes
func SetupRoutes(
	router *gin.RouterGroup,
	clusterSvc ClusterService,
	infobaseSvc InfobaseService,
	sessionSvc SessionService,
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

	// Session management endpoints
	router.GET("/list-sessions", ListSessions(sessionSvc))
	router.POST("/terminate-session", TerminateSession(sessionSvc))
	router.POST("/terminate-sessions", TerminateSessions(sessionSvc))
}
