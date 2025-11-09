package handlers

import (
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/command-center-1c/batch-service/internal/domain/metadata"
	"github.com/command-center-1c/batch-service/internal/domain/storage"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// MetadataHandler handles metadata extraction requests
type MetadataHandler struct {
	extractor      *metadata.Extractor
	storageManager *storage.Manager
	logger         *zap.Logger
}

// NewMetadataHandler creates new MetadataHandler
func NewMetadataHandler(
	extractor *metadata.Extractor,
	storageManager *storage.Manager,
	logger *zap.Logger,
) *MetadataHandler {
	return &MetadataHandler{
		extractor:      extractor,
		storageManager: storageManager,
		logger:         logger,
	}
}

// GetExtensionMetadata handles GET /api/v1/extensions/:file/metadata
// Extracts metadata from specified .cfe file in storage
//
// Path parameter:
//   - file: filename in storage (e.g., "ODataAutoConfig_v1.0.5.cfe")
//
// Response 200:
//
//	{
//	  "name": "ODataAutoConfig",
//	  "version": "1.0.5",
//	  "author": "Developer Name",
//	  "description": "OData auto-configuration extension",
//	  "platform_version_min": "8.3.20.0",
//	  "platform_version_max": "8.3.27.9999",
//	  "dependencies": [],
//	  "size_bytes": 1024000,
//	  "modification_date": "2025-11-08T12:00:00Z",
//	  "checksum_md5": "abc123...",
//	  "objects_count": {
//	    "Catalogs": 5,
//	    "Documents": 3,
//	    "Reports": 2,
//	    "DataProcessors": 1,
//	    ...
//	  }
//	}
//
// Response 400: Invalid filename (not .cfe)
// Response 404: File not found in storage
// Response 500: Internal server error during extraction
func (h *MetadataHandler) GetExtensionMetadata(c *gin.Context) {
	fileName := c.Param("file")

	h.logger.Info("metadata extraction requested",
		zap.String("file", fileName),
		zap.String("client_ip", c.ClientIP()))

	// Step 1: Validate filename (must be .cfe)
	if !strings.HasSuffix(strings.ToLower(fileName), ".cfe") {
		h.logger.Warn("invalid file extension",
			zap.String("file", fileName))
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid file extension",
			"message": "File must be a .cfe extension file",
		})
		return
	}

	// Step 2: Find file in storage
	// Storage structure: storage/extensions/<ExtensionName>/<ExtensionName>_v<Version>.cfe
	// We need to search for the file
	filePath, err := h.findFileInStorage(fileName)
	if err != nil {
		h.logger.Error("file not found in storage",
			zap.String("file", fileName),
			zap.Error(err))
		c.JSON(http.StatusNotFound, gin.H{
			"error":   "File not found",
			"message": fmt.Sprintf("File %s not found in storage", fileName),
		})
		return
	}

	h.logger.Debug("file found in storage",
		zap.String("file", fileName),
		zap.String("path", filePath))

	// Step 3: Extract metadata using Extractor
	metadata, err := h.extractor.ExtractFromCFE(filePath)
	if err != nil {
		h.logger.Error("failed to extract metadata",
			zap.String("file", fileName),
			zap.String("path", filePath),
			zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Metadata extraction failed",
			"message": err.Error(),
		})
		return
	}

	// Step 4: Return metadata as JSON
	h.logger.Info("metadata extraction completed successfully",
		zap.String("file", fileName),
		zap.String("extension_name", metadata.Name),
		zap.String("version", metadata.Version))

	c.JSON(http.StatusOK, metadata)
}

// findFileInStorage searches for file in storage directory
// Storage structure: storage/extensions/<ExtensionName>/<FileName>
// Returns absolute path to file if found
func (h *MetadataHandler) findFileInStorage(fileName string) (string, error) {
	// Get storage base path from manager
	storagePath := h.storageManager.GetStoragePath()

	// List all extensions in storage (pass empty string to get all)
	extensions, err := h.storageManager.ListExtensions("")
	if err != nil {
		return "", fmt.Errorf("failed to list extensions: %w", err)
	}

	// Search for file in each extension directory
	for _, ext := range extensions {
		// Build potential file path using ExtensionName field
		potentialPath := filepath.Join(storagePath, ext.ExtensionName, fileName)

		// Check if file exists
		if fileExists(potentialPath) {
			return potentialPath, nil
		}
	}

	// File not found
	return "", fmt.Errorf("file %s not found in any extension directory", fileName)
}

// fileExists checks if file exists and is not a directory
func fileExists(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return !info.IsDir()
}
