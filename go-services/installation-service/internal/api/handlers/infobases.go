package handlers

import (
	"net/http"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/installation-service/internal/cluster"
	"github.com/gin-gonic/gin"
)

// InfobasesHandler handles infobase-related requests
type InfobasesHandler struct {
	racPath string
	timeout time.Duration
}

// NewInfobasesHandler creates a new InfobasesHandler
func NewInfobasesHandler(racPath string, timeout time.Duration) *InfobasesHandler {
	return &InfobasesHandler{
		racPath: racPath,
		timeout: timeout,
	}
}

// GetInfobases handles GET /api/v1/infobases
// Query params:
//   - server: RAS server address (default: localhost:1545)
//   - cluster_user: cluster admin username (optional)
//   - cluster_pwd: cluster admin password (optional)
//   - detailed: get detailed info (default: false)
func (h *InfobasesHandler) GetInfobases(c *gin.Context) {
	start := time.Now()

	// Parse query parameters
	server := c.DefaultQuery("server", "localhost:1545")
	clusterUser := c.Query("cluster_user")
	clusterPwd := c.Query("cluster_pwd")
	detailed := c.DefaultQuery("detailed", "false") == "true"

	// Validate server parameter (basic validation)
	if server == "" {
		c.JSON(http.StatusBadRequest, cluster.NewErrorResponse(
			"invalid_parameter",
			"server parameter cannot be empty",
		))
		return
	}

	// Create RAC manager
	manager := cluster.NewRACManager(h.racPath, server, clusterUser, clusterPwd, h.timeout)
	defer manager.Close()

	// Get cluster info
	clusterInfo, err := manager.GetClusterInfo(c.Request.Context())
	if err != nil {
		// Determine error code based on error type
		errorCode := "failed_to_get_cluster_info"
		statusCode := http.StatusInternalServerError

		// Check for specific error types
		errMsg := err.Error()
		if strings.Contains(errMsg, "timeout") {
			errorCode = "request_timeout"
			statusCode = http.StatusGatewayTimeout
		} else if strings.Contains(errMsg, "not found") || strings.Contains(errMsg, "executable") {
			errorCode = "rac_not_found"
			statusCode = http.StatusServiceUnavailable
		} else if strings.Contains(errMsg, "connection refused") || strings.Contains(errMsg, "connect") {
			errorCode = "failed_to_connect_to_ras"
			statusCode = http.StatusBadGateway
		}

		c.JSON(statusCode, cluster.NewErrorResponse(errorCode, err.Error()))
		return
	}

	// Get infobase list
	infobases, err := manager.GetInfobaseList(c.Request.Context(), detailed)
	if err != nil {
		// Determine error code based on error type
		errorCode := "failed_to_get_infobase_list"
		statusCode := http.StatusInternalServerError

		errMsg := err.Error()
		if strings.Contains(errMsg, "timeout") {
			errorCode = "request_timeout"
			statusCode = http.StatusGatewayTimeout
		} else if strings.Contains(errMsg, "cluster not found") {
			errorCode = "cluster_not_found"
			statusCode = http.StatusNotFound
		}

		c.JSON(statusCode, cluster.NewErrorResponse(errorCode, err.Error()))
		return
	}

	// Build successful response
	response := cluster.InfobaseListResponse{
		Status:      "success",
		ClusterID:   clusterInfo.UUID,
		ClusterName: clusterInfo.Name,
		TotalCount:  len(infobases),
		Infobases:   infobases,
		DurationMs:  time.Since(start).Milliseconds(),
		Timestamp:   time.Now().Format(time.RFC3339),
	}

	c.JSON(http.StatusOK, response)
}
