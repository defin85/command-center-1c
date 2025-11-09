package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/command-center-1c/batch-service/internal/models"
	"github.com/command-center-1c/batch-service/internal/service"
)

// ExtensionsHandler handles extension-related HTTP requests
type ExtensionsHandler struct {
	installer *service.ExtensionInstaller
	validator *service.FileValidator
}

// NewExtensionsHandler creates a new ExtensionsHandler
func NewExtensionsHandler(installer *service.ExtensionInstaller, validator *service.FileValidator) *ExtensionsHandler {
	return &ExtensionsHandler{
		installer: installer,
		validator: validator,
	}
}

// InstallExtension handles POST /api/v1/extensions/install
// @Summary Install extension to a single infobase
// @Description Installs a 1C extension (.cfe file) to a single infobase
// @Tags extensions
// @Accept json
// @Produce json
// @Param request body models.InstallExtensionRequest true "Installation request"
// @Success 200 {object} models.InstallExtensionResponse
// @Failure 400 {object} ErrorResponse
// @Failure 500 {object} ErrorResponse
// @Router /api/v1/extensions/install [post]
func (h *ExtensionsHandler) InstallExtension(c *gin.Context) {
	var req models.InstallExtensionRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error: "Invalid request body: " + err.Error(),
		})
		return
	}

	// Validate extension file
	if err := h.validator.ValidateExtensionFile(req.ExtensionPath); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error: "File validation failed: " + err.Error(),
		})
		return
	}

	// Install extension
	resp, err := h.installer.InstallExtension(c.Request.Context(), &req)

	if err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error: err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, resp)
}

// BatchInstall handles POST /api/v1/extensions/batch-install
// @Summary Install extension to multiple infobases
// @Description Installs a 1C extension to multiple infobases in parallel
// @Tags extensions
// @Accept json
// @Produce json
// @Param request body models.BatchInstallRequest true "Batch installation request"
// @Success 200 {object} models.BatchInstallResponse
// @Failure 400 {object} ErrorResponse
// @Failure 500 {object} ErrorResponse
// @Router /api/v1/extensions/batch-install [post]
func (h *ExtensionsHandler) BatchInstall(c *gin.Context) {
	var req models.BatchInstallRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error: "Invalid request body: " + err.Error(),
		})
		return
	}

	// Batch install
	resp := h.installer.BatchInstall(c.Request.Context(), &req)

	c.JSON(http.StatusOK, resp)
}

// ErrorResponse represents an error response
type ErrorResponse struct {
	Error string `json:"error"`
}
