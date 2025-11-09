package storage

import (
	"bytes"
	"fmt"
	"io"
	"path/filepath"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/command-center-1c/batch-service/internal/infrastructure/filesystem"
	"github.com/command-center-1c/batch-service/internal/models"
)

// Manager управляет хранилищем расширений (.cfe файлов)
type Manager struct {
	logger          *zap.Logger
	storage         *filesystem.Storage
	metadata        *filesystem.MetadataManager
	cleanup         *CleanupManager
	retentionCount  int // Количество версий для хранения (по умолчанию 3)
}

// NewManager создает новый экземпляр Manager
func NewManager(
	storagePath string,
	retentionCount int,
	logger *zap.Logger,
) *Manager {
	storage := filesystem.NewStorage(storagePath, logger)
	metadata := filesystem.NewMetadataManager(storagePath, logger)
	cleanup := NewCleanupManager(logger)

	return &Manager{
		logger:         logger,
		storage:        storage,
		metadata:       metadata,
		cleanup:        cleanup,
		retentionCount: retentionCount,
	}
}

// SaveExtension сохраняет новый файл расширения в storage
// file - поток данных .cfe файла
// name - имя расширения (опционально, если пустое - извлекается из fileName)
// version - версия (опционально, если пустая - извлекается из fileName)
// author - автор загрузки (опционально)
func (m *Manager) SaveExtension(file io.Reader, fileName, name, version, author string) (*models.StoredExtension, error) {
	// Валидация имени файла
	if err := ValidateFileName(fileName); err != nil {
		return nil, fmt.Errorf("invalid file name: %w", err)
	}

	// Парсим имя файла чтобы извлечь extension_name и version (если не указаны)
	parsedName, parsedVersion, err := ParseVersion(fileName)
	if err != nil {
		return nil, fmt.Errorf("failed to parse file name: %w", err)
	}

	// Если name не указан, используем распарсенный
	if name == "" {
		name = parsedName
	}

	// Если version не указана, используем распарсенную
	if version == "" {
		version = parsedVersion
	}

	// Проверяем что распарсенное имя совпадает с указанным (если указано)
	if name != parsedName {
		return nil, fmt.Errorf("extension name mismatch: file name suggests '%s', but '%s' provided",
			parsedName, name)
	}

	// Проверяем что распарсенная версия совпадает с указанной (если указана)
	if version != parsedVersion {
		return nil, fmt.Errorf("version mismatch: file name suggests '%s', but '%s' provided",
			parsedVersion, version)
	}

	m.logger.Info("saving extension",
		zap.String("file_name", fileName),
		zap.String("extension_name", name),
		zap.String("version", version),
		zap.String("author", author))

	// Вычисляем MD5 checksum (нужно прочитать поток дважды)
	// Читаем в буфер чтобы можно было использовать дважды
	var buf bytes.Buffer
	tee := io.TeeReader(file, &buf)

	// Вычисляем checksum
	checksum, err := m.metadata.CalculateMD5(tee)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate checksum: %w", err)
	}

	// Сохраняем файл (используем buf который содержит все данные)
	destPath := filepath.Join(name, fileName)
	size, err := m.storage.SaveFile(&buf, destPath)
	if err != nil {
		return nil, fmt.Errorf("failed to save file: %w", err)
	}

	// Создаем StoredExtension запись
	extension := &models.StoredExtension{
		FileName:      fileName,
		ExtensionName: name,
		Version:       version,
		Author:        author,
		SizeBytes:     size,
		ChecksumMD5:   checksum,
		UploadedAt:    time.Now(),
		FilePath:      filepath.Join(m.storage.GetStoragePath(), destPath),
	}

	// Загружаем текущие метаданные
	existingVersions, err := m.metadata.LoadMetadata(name)
	if err != nil {
		return nil, fmt.Errorf("failed to load metadata: %w", err)
	}

	// Проверяем не существует ли уже такая версия
	for _, existing := range existingVersions {
		if existing.Version == version {
			// Версия уже существует - можем либо перезаписать, либо вернуть ошибку
			m.logger.Warn("version already exists, overwriting",
				zap.String("extension_name", name),
				zap.String("version", version))
			// Удаляем старую запись из списка
			existingVersions = removeVersion(existingVersions, version)
			break
		}
	}

	// Добавляем новую версию
	allVersions := append(existingVersions, *extension)

	// Применяем retention policy (удаляем старые версии)
	if err := m.applyRetentionPolicy(name, allVersions); err != nil {
		return nil, fmt.Errorf("failed to apply retention policy: %w", err)
	}

	m.logger.Info("extension saved successfully",
		zap.String("file_name", fileName),
		zap.String("extension_name", name),
		zap.String("version", version),
		zap.Int64("size_bytes", size),
		zap.String("checksum", checksum))

	return extension, nil
}

// GetExtension получает метаданные расширения по fileName
func (m *Manager) GetExtension(fileName string) (*models.StoredExtension, error) {
	// Парсим имя файла
	name, version, err := ParseVersion(fileName)
	if err != nil {
		return nil, fmt.Errorf("failed to parse file name: %w", err)
	}

	// Загружаем метаданные
	versions, err := m.metadata.LoadMetadata(name)
	if err != nil {
		return nil, fmt.Errorf("failed to load metadata: %w", err)
	}

	// Ищем нужную версию
	for _, ext := range versions {
		if ext.Version == version {
			return &ext, nil
		}
	}

	return nil, fmt.Errorf("extension not found: %s", fileName)
}

// ListExtensions возвращает список всех расширений
// extensionName - опциональный фильтр по имени расширения
func (m *Manager) ListExtensions(extensionName string) ([]models.StoredExtension, error) {
	var result []models.StoredExtension

	if extensionName != "" {
		// Если указано имя расширения, загружаем только его версии
		versions, err := m.metadata.LoadMetadata(extensionName)
		if err != nil {
			return nil, fmt.Errorf("failed to load metadata for %s: %w", extensionName, err)
		}
		result = versions
	} else {
		// Если имя не указано, загружаем все расширения из корня storage
		// Получаем список директорий в корне storage
		files, err := m.storage.ListFiles("")
		if err != nil {
			return nil, fmt.Errorf("failed to list storage root: %w", err)
		}

		// Для каждой директории загружаем метаданные
		for _, fileInfo := range files {
			if !fileInfo.IsDir() {
				continue
			}

			name := fileInfo.Name()
			versions, err := m.metadata.LoadMetadata(name)
			if err != nil {
				m.logger.Warn("failed to load metadata for extension",
					zap.String("extension_name", name),
					zap.Error(err))
				continue
			}

			result = append(result, versions...)
		}
	}

	m.logger.Debug("listed extensions",
		zap.String("filter", extensionName),
		zap.Int("count", len(result)))

	return result, nil
}

// DeleteExtension удаляет расширение из storage
func (m *Manager) DeleteExtension(fileName string) error {
	// Парсим имя файла
	name, version, err := ParseVersion(fileName)
	if err != nil {
		return fmt.Errorf("failed to parse file name: %w", err)
	}

	m.logger.Info("deleting extension",
		zap.String("file_name", fileName),
		zap.String("extension_name", name),
		zap.String("version", version))

	// Удаляем файл
	filePath := filepath.Join(name, fileName)
	if err := m.storage.DeleteFile(filePath); err != nil {
		return fmt.Errorf("failed to delete file: %w", err)
	}

	// Загружаем метаданные
	versions, err := m.metadata.LoadMetadata(name)
	if err != nil {
		return fmt.Errorf("failed to load metadata: %w", err)
	}

	// Удаляем версию из метаданных
	updatedVersions := removeVersion(versions, version)

	// Сохраняем обновленные метаданные
	if err := m.metadata.SaveMetadata(name, updatedVersions); err != nil {
		return fmt.Errorf("failed to save metadata: %w", err)
	}

	m.logger.Info("extension deleted successfully",
		zap.String("file_name", fileName))

	return nil
}

// applyRetentionPolicy применяет политику удержания версий
// Удаляет старые версии, оставляя только последние retentionCount версий
func (m *Manager) applyRetentionPolicy(extensionName string, allVersions []models.StoredExtension) error {
	// Определяем какие версии нужно удалить
	toDelete, err := m.cleanup.CleanupOldVersions(allVersions, m.retentionCount)
	if err != nil {
		return fmt.Errorf("failed to calculate versions to delete: %w", err)
	}

	// Удаляем старые файлы
	for _, ext := range toDelete {
		filePath := filepath.Join(extensionName, ext.FileName)
		if err := m.storage.DeleteFile(filePath); err != nil {
			m.logger.Error("failed to delete old version",
				zap.String("file_name", ext.FileName),
				zap.Error(err))
			// Продолжаем удаление остальных версий даже при ошибке
		} else {
			m.logger.Info("deleted old version",
				zap.String("file_name", ext.FileName),
				zap.String("version", ext.Version))
		}
	}

	// Получаем список версий которые остаются
	versionsToKeep := m.cleanup.GetVersionsToKeep(allVersions, m.retentionCount)

	// Сохраняем обновленные метаданные
	if err := m.metadata.SaveMetadata(extensionName, versionsToKeep); err != nil {
		return fmt.Errorf("failed to save metadata after cleanup: %w", err)
	}

	return nil
}

// GetStoragePath returns the storage base path
func (m *Manager) GetStoragePath() string {
	return m.storage.GetStoragePath()
}

// removeVersion удаляет версию из списка
func removeVersion(versions []models.StoredExtension, version string) []models.StoredExtension {
	result := make([]models.StoredExtension, 0, len(versions))
	for _, v := range versions {
		if !strings.EqualFold(v.Version, version) {
			result = append(result, v)
		}
	}
	return result
}
