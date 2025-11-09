package filesystem

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"go.uber.org/zap"

	"github.com/command-center-1c/batch-service/internal/models"
)

// MetadataManager управляет metadata.json файлами для расширений
type MetadataManager struct {
	logger      *zap.Logger
	storagePath string
}

// NewMetadataManager создает новый экземпляр MetadataManager
func NewMetadataManager(storagePath string, logger *zap.Logger) *MetadataManager {
	return &MetadataManager{
		logger:      logger,
		storagePath: storagePath,
	}
}

// ExtensionMetadata представляет структуру metadata.json для расширения
type ExtensionMetadata struct {
	ExtensionName string                    `json:"extension_name"`
	Versions      []models.StoredExtension  `json:"versions"`
}

// SaveMetadata сохраняет metadata.json для расширения
func (m *MetadataManager) SaveMetadata(extName string, extensions []models.StoredExtension) error {
	// Путь к metadata.json
	metadataPath := filepath.Join(m.storagePath, extName, "metadata.json")

	// Создаем структуру
	metadata := ExtensionMetadata{
		ExtensionName: extName,
		Versions:      extensions,
	}

	// Сериализуем в JSON с отступами для читаемости
	data, err := json.MarshalIndent(metadata, "", "  ")
	if err != nil {
		m.logger.Error("failed to marshal metadata",
			zap.String("extension", extName),
			zap.Error(err))
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	// Создаем директорию если не существует
	dir := filepath.Dir(metadataPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		m.logger.Error("failed to create directory for metadata",
			zap.String("path", dir),
			zap.Error(err))
		return fmt.Errorf("failed to create directory: %w", err)
	}

	// Записываем файл
	if err := os.WriteFile(metadataPath, data, 0644); err != nil {
		m.logger.Error("failed to write metadata file",
			zap.String("path", metadataPath),
			zap.Error(err))
		return fmt.Errorf("failed to write metadata file: %w", err)
	}

	m.logger.Info("metadata saved successfully",
		zap.String("extension", extName),
		zap.Int("versions_count", len(extensions)))

	return nil
}

// LoadMetadata загружает metadata.json для расширения
func (m *MetadataManager) LoadMetadata(extName string) ([]models.StoredExtension, error) {
	metadataPath := filepath.Join(m.storagePath, extName, "metadata.json")

	// Проверяем существует ли файл
	if _, err := os.Stat(metadataPath); os.IsNotExist(err) {
		// Если файла нет, возвращаем пустой список (не ошибку)
		m.logger.Debug("metadata file not found, returning empty list",
			zap.String("extension", extName))
		return []models.StoredExtension{}, nil
	}

	// Читаем файл
	data, err := os.ReadFile(metadataPath)
	if err != nil {
		m.logger.Error("failed to read metadata file",
			zap.String("path", metadataPath),
			zap.Error(err))
		return nil, fmt.Errorf("failed to read metadata file: %w", err)
	}

	// Парсим JSON
	var metadata ExtensionMetadata
	if err := json.Unmarshal(data, &metadata); err != nil {
		m.logger.Error("failed to unmarshal metadata",
			zap.String("path", metadataPath),
			zap.Error(err))
		return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
	}

	m.logger.Debug("metadata loaded successfully",
		zap.String("extension", extName),
		zap.Int("versions_count", len(metadata.Versions)))

	return metadata.Versions, nil
}

// CalculateMD5 вычисляет MD5 checksum для потока данных
// ВАЖНО: эта функция читает весь поток, поэтому нужно использовать io.TeeReader
// если данные нужно прочитать дважды
func (m *MetadataManager) CalculateMD5(file io.Reader) (string, error) {
	hash := md5.New()

	if _, err := io.Copy(hash, file); err != nil {
		m.logger.Error("failed to calculate MD5",
			zap.Error(err))
		return "", fmt.Errorf("failed to calculate MD5: %w", err)
	}

	checksum := hex.EncodeToString(hash.Sum(nil))

	m.logger.Debug("MD5 calculated",
		zap.String("checksum", checksum))

	return checksum, nil
}

// CalculateFileMD5 вычисляет MD5 checksum для существующего файла
func (m *MetadataManager) CalculateFileMD5(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		m.logger.Error("failed to open file for MD5",
			zap.String("path", filePath),
			zap.Error(err))
		return "", fmt.Errorf("failed to open file: %w", err)
	}
	defer file.Close()

	return m.CalculateMD5(file)
}
