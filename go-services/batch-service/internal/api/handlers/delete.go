package handlers

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/command-center-1c/batch-service/internal/service"
)

// DeleteExtensionHandler handles DELETE /api/v1/extensions/delete
type DeleteExtensionHandler struct {
	deleter *service.ExtensionDeleter
}

// NewDeleteExtensionHandler creates a new DeleteExtensionHandler
func NewDeleteExtensionHandler(deleter *service.ExtensionDeleter) *DeleteExtensionHandler {
	return &DeleteExtensionHandler{
		deleter: deleter,
	}
}

// DeleteExtensionRequest represents a request to delete extension
type DeleteExtensionRequest struct {
	Server        string `json:"server" binding:"required"`
	InfobaseName  string `json:"infobase_name" binding:"required"`
	Username      string `json:"username" binding:"required"`
	Password      string `json:"password" binding:"required"`
	ExtensionName string `json:"extension_name" binding:"required"`
}

// DeleteExtensionResponse represents the response from extension deletion
type DeleteExtensionResponse struct {
	Message       string `json:"message"`
	ExtensionName string `json:"extension_name"`
}

// Delete handles POST /api/v1/extensions/delete
// @Summary Delete extension from a single infobase
// @Description Deletes a 1C extension from a single infobase
// @Tags extensions
// @Accept json
// @Produce json
// @Param request body DeleteExtensionRequest true "Deletion request"
// @Success 200 {object} DeleteExtensionResponse
// @Failure 400 {object} ErrorResponse
// @Failure 500 {object} ErrorResponse
// @Router /api/v1/extensions/delete [post]
func (h *DeleteExtensionHandler) Delete(c *gin.Context) {
	var req DeleteExtensionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error: "Invalid request body: " + err.Error(),
		})
		return
	}

	log.Printf("Deleting extension '%s' from '%s\\%s'",
		req.ExtensionName,
		req.Server,
		req.InfobaseName,
	)

	deleteReq := service.DeleteRequest{
		Server:        req.Server,
		InfobaseName:  req.InfobaseName,
		Username:      req.Username,
		Password:      req.Password,
		ExtensionName: req.ExtensionName,
	}

	err := h.deleter.DeleteExtension(c.Request.Context(), deleteReq)
	if err != nil {
		log.Printf("Failed to delete extension: %v", err)
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error: err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, DeleteExtensionResponse{
		Message:       "Extension deleted successfully",
		ExtensionName: req.ExtensionName,
	})
}
