package filesystem

import (
	"fmt"
	"io"
	"os"
	"path/filepath"

	"go.uber.org/zap"
)

// Storage предоставляет операции с файловой системой для хранилища расширений
type Storage struct {
	logger      *zap.Logger
	storagePath string // Корневой путь к storage (например, ./storage/extensions)
}

// NewStorage создает новый экземпляр Storage
func NewStorage(storagePath string, logger *zap.Logger) *Storage {
	return &Storage{
		logger:      logger,
		storagePath: storagePath,
	}
}

// SaveFile сохраняет файл по указанному пути и возвращает его размер
// destPath - относительный путь внутри storage (например, ODataAutoConfig/file.cfe)
func (s *Storage) SaveFile(file io.Reader, destPath string) (int64, error) {
	// Полный путь к файлу
	fullPath := filepath.Join(s.storagePath, destPath)

	// Создаем директорию если не существует
	dir := filepath.Dir(fullPath)
	if err := s.EnsureDir(dir); err != nil {
		return 0, fmt.Errorf("failed to create directory: %w", err)
	}

	// Создаем файл
	outFile, err := os.Create(fullPath)
	if err != nil {
		s.logger.Error("failed to create file",
			zap.String("path", fullPath),
			zap.Error(err))
		return 0, fmt.Errorf("failed to create file: %w", err)
	}
	defer outFile.Close()

	// Копируем данные
	size, err := io.Copy(outFile, file)
	if err != nil {
		s.logger.Error("failed to write file",
			zap.String("path", fullPath),
			zap.Error(err))
		return 0, fmt.Errorf("failed to write file: %w", err)
	}

	s.logger.Info("file saved successfully",
		zap.String("path", fullPath),
		zap.Int64("size", size))

	return size, nil
}

// GetFile открывает файл для чтения
// path - относительный путь внутри storage
func (s *Storage) GetFile(path string) (io.ReadCloser, error) {
	fullPath := filepath.Join(s.storagePath, path)

	file, err := os.Open(fullPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("file not found: %s", path)
		}
		s.logger.Error("failed to open file",
			zap.String("path", fullPath),
			zap.Error(err))
		return nil, fmt.Errorf("failed to open file: %w", err)
	}

	return file, nil
}

// DeleteFile удаляет файл по указанному пути
// path - относительный путь внутри storage
func (s *Storage) DeleteFile(path string) error {
	fullPath := filepath.Join(s.storagePath, path)

	if err := os.Remove(fullPath); err != nil {
		if os.IsNotExist(err) {
			return fmt.Errorf("file not found: %s", path)
		}
		s.logger.Error("failed to delete file",
			zap.String("path", fullPath),
			zap.Error(err))
		return fmt.Errorf("failed to delete file: %w", err)
	}

	s.logger.Info("file deleted successfully",
		zap.String("path", fullPath))

	return nil
}

// ListFiles возвращает список файлов в указанной директории
// dirPath - относительный путь внутри storage
func (s *Storage) ListFiles(dirPath string) ([]os.FileInfo, error) {
	fullPath := filepath.Join(s.storagePath, dirPath)

	// Проверяем что директория существует
	if _, err := os.Stat(fullPath); os.IsNotExist(err) {
		// Если директория не существует, возвращаем пустой список (не ошибку)
		return []os.FileInfo{}, nil
	}

	entries, err := os.ReadDir(fullPath)
	if err != nil {
		s.logger.Error("failed to list directory",
			zap.String("path", fullPath),
			zap.Error(err))
		return nil, fmt.Errorf("failed to list directory: %w", err)
	}

	// Конвертируем DirEntry в FileInfo
	fileInfos := make([]os.FileInfo, 0, len(entries))
	for _, entry := range entries {
		info, err := entry.Info()
		if err != nil {
			s.logger.Warn("failed to get file info",
				zap.String("name", entry.Name()),
				zap.Error(err))
			continue
		}
		fileInfos = append(fileInfos, info)
	}

	return fileInfos, nil
}

// EnsureDir создает директорию со всеми родительскими директориями если они не существуют
func (s *Storage) EnsureDir(path string) error {
	if err := os.MkdirAll(path, 0755); err != nil {
		s.logger.Error("failed to create directory",
			zap.String("path", path),
			zap.Error(err))
		return fmt.Errorf("failed to create directory: %w", err)
	}
	return nil
}

// GetStoragePath возвращает корневой путь к storage
func (s *Storage) GetStoragePath() string {
	return s.storagePath
}
