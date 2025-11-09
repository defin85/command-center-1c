package storage

import (
	"fmt"
	"sort"

	"go.uber.org/zap"

	"github.com/command-center-1c/batch-service/internal/models"
)

// CleanupManager управляет политикой удержания версий (retention policy)
type CleanupManager struct {
	logger *zap.Logger
}

// NewCleanupManager создает новый экземпляр CleanupManager
func NewCleanupManager(logger *zap.Logger) *CleanupManager {
	return &CleanupManager{
		logger: logger,
	}
}

// CleanupOldVersions удаляет старые версии расширения, оставляя только последние N версий
// extensions - текущий список версий расширения
// keepCount - количество версий которое нужно оставить (например, 3)
// Возвращает список версий которые нужно удалить из storage
func (c *CleanupManager) CleanupOldVersions(extensions []models.StoredExtension, keepCount int) ([]models.StoredExtension, error) {
	// Если версий меньше или равно keepCount, удалять нечего
	if len(extensions) <= keepCount {
		c.logger.Debug("no cleanup needed",
			zap.Int("current_versions", len(extensions)),
			zap.Int("keep_count", keepCount))
		return []models.StoredExtension{}, nil
	}

	// Сортируем версии по semantic version (от новых к старым)
	sortedVersions := make([]models.StoredExtension, len(extensions))
	copy(sortedVersions, extensions)

	sort.Slice(sortedVersions, func(i, j int) bool {
		cmp, err := CompareVersions(sortedVersions[i].Version, sortedVersions[j].Version)
		if err != nil {
			c.logger.Warn("failed to compare versions, fallback to string comparison",
				zap.String("v1", sortedVersions[i].Version),
				zap.String("v2", sortedVersions[j].Version),
				zap.Error(err))
			// Fallback к строковому сравнению
			return sortedVersions[i].Version > sortedVersions[j].Version
		}
		return cmp > 0 // Сортировка по убыванию (новые первые)
	})

	// Версии которые нужно удалить (всё что за пределами keepCount)
	toDelete := sortedVersions[keepCount:]

	c.logger.Info("cleanup identified old versions",
		zap.Int("total_versions", len(extensions)),
		zap.Int("keep_count", keepCount),
		zap.Int("to_delete", len(toDelete)))

	for _, ext := range toDelete {
		c.logger.Debug("marked for deletion",
			zap.String("file_name", ext.FileName),
			zap.String("version", ext.Version))
	}

	return toDelete, nil
}

// GetVersionsToKeep возвращает список версий которые нужно оставить (последние N версий)
// extensions - текущий список версий
// keepCount - количество версий которое нужно оставить
func (c *CleanupManager) GetVersionsToKeep(extensions []models.StoredExtension, keepCount int) []models.StoredExtension {
	if len(extensions) <= keepCount {
		return extensions
	}

	// Сортируем версии по semantic version (от новых к старым)
	sortedVersions := make([]models.StoredExtension, len(extensions))
	copy(sortedVersions, extensions)

	sort.Slice(sortedVersions, func(i, j int) bool {
		cmp, err := CompareVersions(sortedVersions[i].Version, sortedVersions[j].Version)
		if err != nil {
			c.logger.Warn("failed to compare versions, fallback to string comparison",
				zap.String("v1", sortedVersions[i].Version),
				zap.String("v2", sortedVersions[j].Version),
				zap.Error(err))
			return sortedVersions[i].Version > sortedVersions[j].Version
		}
		return cmp > 0 // Сортировка по убыванию (новые первые)
	})

	// Берем только последние keepCount версий
	toKeep := sortedVersions[:keepCount]

	c.logger.Debug("versions to keep",
		zap.Int("keep_count", len(toKeep)))

	return toKeep
}

// ValidateRetentionPolicy проверяет что политика удержания соблюдена
// extensions - текущий список версий
// keepCount - ожидаемое количество версий
func (c *CleanupManager) ValidateRetentionPolicy(extensions []models.StoredExtension, keepCount int) error {
	if len(extensions) > keepCount {
		return fmt.Errorf("retention policy violated: expected max %d versions, got %d",
			keepCount, len(extensions))
	}
	return nil
}
