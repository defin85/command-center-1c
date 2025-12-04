package routes

import (
	"github.com/gin-gonic/gin"
)

// RegisterRASRoutes registers all RAS Adapter routes to the given router group
// This includes infobase management, session management, and cluster operations
func RegisterRASRoutes(rg *gin.RouterGroup, rasHandler gin.HandlerFunc) {
	// RAS Adapter routes - Infobase management via /infobases/ group
	infobases := rg.Group("/infobases")
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
	sessions := rg.Group("/sessions")
	{
		sessions.GET("/list-sessions", rasHandler)
		sessions.POST("/terminate-session", rasHandler)
		sessions.POST("/terminate-sessions", rasHandler)
	}

	// Legacy flat routes (for backward compatibility)
	rg.GET("/list-clusters", rasHandler)
	rg.GET("/get-cluster", rasHandler)
	rg.GET("/list-infobases", rasHandler)
	rg.GET("/get-infobase", rasHandler)
	rg.POST("/create-infobase", rasHandler)
	rg.POST("/drop-infobase", rasHandler)
	rg.POST("/lock-infobase", rasHandler)
	rg.POST("/unlock-infobase", rasHandler)
	rg.POST("/block-sessions", rasHandler)
	rg.POST("/unblock-sessions", rasHandler)
	rg.GET("/list-sessions", rasHandler)
	rg.POST("/terminate-session", rasHandler)
	rg.POST("/terminate-sessions", rasHandler)
}
