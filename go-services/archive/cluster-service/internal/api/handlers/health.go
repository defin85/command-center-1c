package handlers

import (
	"net/http"

	"github.com/command-center-1c/cluster-service/internal/models"
	"github.com/command-center-1c/cluster-service/internal/version"
	"github.com/gin-gonic/gin"
)

type HealthHandler struct{}

func NewHealthHandler() *HealthHandler {
	return &HealthHandler{}
}

func (h *HealthHandler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, models.HealthResponse{
		Status:  "healthy",
		Service: "cluster-service",
		Version: version.Version,
	})
}
