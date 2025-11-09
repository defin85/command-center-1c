package handlers

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/command-center-1c/batch-service/internal/service"
)

// ListExtensionsHandler handles GET /api/v1/extensions/list
type ListExtensionsHandler struct {
	lister *service.ExtensionLister
}

// NewListExtensionsHandler creates a new ListExtensionsHandler
func NewListExtensionsHandler(lister *service.ExtensionLister) *ListExtensionsHandler {
	return &ListExtensionsHandler{
		lister: lister,
	}
}

// ListExtensionsRequest represents query parameters for listing extensions
type ListExtensionsRequest struct {
	Server       string `form:"server" binding:"required"`
	InfobaseName string `form:"infobase_name" binding:"required"`
	Username     string `form:"username" binding:"required"`
	Password     string `form:"password" binding:"required"`
}

// ListExtensionsResponse represents the response from listing extensions
type ListExtensionsResponse struct {
	Extensions []service.ExtensionInfo `json:"extensions"`
	Count      int                     `json:"count"`
	Warning    string                  `json:"warning,omitempty"`
}

// List handles GET /api/v1/extensions/list
// @Summary List extensions in an infobase
// @Description Returns a list of all extensions installed in the specified infobase
// @Tags extensions
// @Accept json
// @Produce json
// @Param server query string true "Server address (e.g., localhost:1541)"
// @Param infobase_name query string true "Infobase name"
// @Param username query string true "Username"
// @Param password query string true "Password"
// @Success 200 {object} ListExtensionsResponse
// @Failure 400 {object} ErrorResponse
// @Failure 500 {object} ErrorResponse
// @Router /api/v1/extensions/list [get]
func (h *ListExtensionsHandler) List(c *gin.Context) {
	var req ListExtensionsRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error: "Invalid query parameters: " + err.Error(),
		})
		return
	}

	log.Printf("Listing extensions from '%s\\%s'",
		req.Server,
		req.InfobaseName,
	)

	listReq := service.ListRequest{
		Server:       req.Server,
		InfobaseName: req.InfobaseName,
		Username:     req.Username,
		Password:     req.Password,
	}

	extensions, err := h.lister.ListExtensions(c.Request.Context(), listReq)
	if err != nil {
		log.Printf("Failed to list extensions: %v", err)
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error: err.Error(),
		})
		return
	}

	response := ListExtensionsResponse{
		Extensions: extensions,
		Count:      len(extensions),
	}

	// Add warning if using stub implementation
	if len(extensions) == 0 {
		response.Warning = "ListExtensions is using stub implementation. ConfigurationRepositoryReport format requires empirical testing on real 1C database."
	}

	c.JSON(http.StatusOK, response)
}
