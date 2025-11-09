package handlers

import (
	"fmt"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/command-center-1c/batch-service/internal/domain/storage"
	"github.com/command-center-1c/batch-service/internal/models"
)

const (
	// Лимиты для загрузки файлов
	maxUploadSize  = 100 * 1024 * 1024 // 100 MB
	minUploadSize  = 1                  // 1 byte
)

// StorageHandler управляет HTTP запросами для storage API
type StorageHandler struct {
	logger         *zap.Logger
	storageManager *storage.Manager
}

// NewStorageHandler создает новый экземпляр StorageHandler
func NewStorageHandler(storageManager *storage.Manager, logger *zap.Logger) *StorageHandler {
	return &StorageHandler{
		logger:         logger,
		storageManager: storageManager,
	}
}

// UploadExtension обрабатывает POST /api/v1/extensions/storage/upload
// Загружает .cfe файл расширения в хранилище
func (h *StorageHandler) UploadExtension(c *gin.Context) {
	h.logger.Info("upload extension request received")

	// Получаем файл из multipart form
	file, header, err := c.Request.FormFile("file")
	if err != nil {
		h.logger.Error("failed to get file from request",
			zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "file is required",
			"details": err.Error(),
		})
		return
	}
	defer file.Close()

	// Проверяем размер файла
	if header.Size < minUploadSize {
		h.logger.Warn("file size too small",
			zap.Int64("size", header.Size))
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "file size too small",
			"details": fmt.Sprintf("minimum size: %d bytes", minUploadSize),
		})
		return
	}

	if header.Size > maxUploadSize {
		h.logger.Warn("file size too large",
			zap.Int64("size", header.Size),
			zap.Int64("max", maxUploadSize))
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "file size too large",
			"details": fmt.Sprintf("maximum size: %d MB", maxUploadSize/(1024*1024)),
		})
		return
	}

	// Получаем имя файла и sanitize
	fileName := storage.SanitizeFileName(header.Filename)

	// Валидация имени файла
	if err := storage.ValidateFileName(fileName); err != nil {
		h.logger.Warn("invalid file name",
			zap.String("file_name", fileName),
			zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "invalid file name",
			"details": err.Error(),
		})
		return
	}

	// Получаем опциональные параметры из form
	extensionName := c.PostForm("extension_name")
	version := c.PostForm("version")
	author := c.PostForm("author")

	h.logger.Info("uploading extension",
		zap.String("file_name", fileName),
		zap.String("extension_name", extensionName),
		zap.String("version", version),
		zap.String("author", author),
		zap.Int64("size", header.Size))

	// Сохраняем файл
	extension, err := h.storageManager.SaveExtension(file, fileName, extensionName, version, author)
	if err != nil {
		h.logger.Error("failed to save extension",
			zap.String("file_name", fileName),
			zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "failed to save extension",
			"details": err.Error(),
		})
		return
	}

	// Формируем ответ
	response := models.UploadResponse{
		Success:     true,
		FileName:    extension.FileName,
		Path:        extension.FilePath,
		SizeBytes:   extension.SizeBytes,
		ChecksumMD5: extension.ChecksumMD5,
		UploadedAt:  extension.UploadedAt,
	}

	h.logger.Info("extension uploaded successfully",
		zap.String("file_name", extension.FileName),
		zap.String("extension_name", extension.ExtensionName),
		zap.String("version", extension.Version))

	c.JSON(http.StatusOK, response)
}

// ListStorage обрабатывает GET /api/v1/extensions/storage
// Возвращает список всех расширений в хранилище
func (h *StorageHandler) ListStorage(c *gin.Context) {
	// Опциональный фильтр по имени расширения
	extensionName := c.Query("extension_name")

	h.logger.Info("list storage request",
		zap.String("filter", extensionName))

	// Получаем список расширений
	extensions, err := h.storageManager.ListExtensions(extensionName)
	if err != nil {
		h.logger.Error("failed to list extensions",
			zap.String("filter", extensionName),
			zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "failed to list extensions",
			"details": err.Error(),
		})
		return
	}

	// Формируем ответ
	response := models.StorageListResponse{
		Extensions: extensions,
		TotalCount: len(extensions),
	}

	h.logger.Info("storage listed successfully",
		zap.String("filter", extensionName),
		zap.Int("count", len(extensions)))

	c.JSON(http.StatusOK, response)
}

// GetExtensionMetadata обрабатывает GET /api/v1/extensions/storage/:name
// Возвращает метаданные конкретного расширения
func (h *StorageHandler) GetExtensionMetadata(c *gin.Context) {
	fileName := c.Param("name")

	// Удаляем возможные пробелы
	fileName = strings.TrimSpace(fileName)

	if fileName == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "file name is required",
		})
		return
	}

	h.logger.Info("get extension metadata request",
		zap.String("file_name", fileName))

	// Получаем метаданные
	extension, err := h.storageManager.GetExtension(fileName)
	if err != nil {
		h.logger.Error("failed to get extension",
			zap.String("file_name", fileName),
			zap.Error(err))

		// Проверяем тип ошибки
		if strings.Contains(err.Error(), "not found") {
			c.JSON(http.StatusNotFound, gin.H{
				"error": "extension not found",
				"details": err.Error(),
			})
			return
		}

		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "failed to get extension",
			"details": err.Error(),
		})
		return
	}

	h.logger.Info("extension metadata retrieved",
		zap.String("file_name", fileName))

	c.JSON(http.StatusOK, extension)
}

// DeleteExtension обрабатывает DELETE /api/v1/extensions/storage/:name
// Удаляет файл расширения из хранилища
func (h *StorageHandler) DeleteExtension(c *gin.Context) {
	fileName := c.Param("name")

	// Удаляем возможные пробелы
	fileName = strings.TrimSpace(fileName)

	if fileName == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "file name is required",
		})
		return
	}

	h.logger.Info("delete extension request",
		zap.String("file_name", fileName))

	// Удаляем расширение
	if err := h.storageManager.DeleteExtension(fileName); err != nil {
		h.logger.Error("failed to delete extension",
			zap.String("file_name", fileName),
			zap.Error(err))

		// Проверяем тип ошибки
		if strings.Contains(err.Error(), "not found") {
			c.JSON(http.StatusNotFound, gin.H{
				"error": "extension not found",
				"details": err.Error(),
			})
			return
		}

		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "failed to delete extension",
			"details": err.Error(),
		})
		return
	}

	// Формируем ответ
	response := models.DeleteResponse{
		Success:     true,
		Message:     "Extension file deleted successfully",
		DeletedFile: fileName,
	}

	h.logger.Info("extension deleted successfully",
		zap.String("file_name", fileName))

	c.JSON(http.StatusOK, response)
}
