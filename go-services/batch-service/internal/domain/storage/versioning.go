package storage

import (
	"fmt"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/hashicorp/go-version"
)

// ParseVersion парсит имя файла и извлекает имя расширения и версию
// Формат: {ExtensionName}_v{SemanticVersion}.cfe
// Примеры:
//   - ODataAutoConfig_v1.0.5.cfe → name="ODataAutoConfig", version="1.0.5"
//   - MobileApp_v2.1.3.cfe → name="MobileApp", version="2.1.3"
func ParseVersion(fileName string) (name, versionStr string, err error) {
	// Удаляем расширение .cfe
	baseName := strings.TrimSuffix(fileName, ".cfe")
	if baseName == fileName {
		return "", "", fmt.Errorf("file must have .cfe extension")
	}

	// Regex для парсинга: {Name}_v{Version}
	// Поддерживает семантическое версионирование: major.minor.patch
	re := regexp.MustCompile(`^(.+?)_v(\d+\.\d+\.\d+)$`)
	matches := re.FindStringSubmatch(baseName)

	if len(matches) != 3 {
		return "", "", fmt.Errorf("invalid file name format, expected: {Name}_v{Version}.cfe")
	}

	name = matches[1]
	versionStr = matches[2]

	// Валидация версии через go-version
	if _, err := version.NewVersion(versionStr); err != nil {
		return "", "", fmt.Errorf("invalid semantic version: %w", err)
	}

	return name, versionStr, nil
}

// CompareVersions сравнивает две semantic версии
// Возвращает:
//   -1 если v1 < v2
//    0 если v1 == v2
//    1 если v1 > v2
func CompareVersions(v1Str, v2Str string) (int, error) {
	v1, err := version.NewVersion(v1Str)
	if err != nil {
		return 0, fmt.Errorf("invalid version v1: %w", err)
	}

	v2, err := version.NewVersion(v2Str)
	if err != nil {
		return 0, fmt.Errorf("invalid version v2: %w", err)
	}

	return v1.Compare(v2), nil
}

// GenerateFileName генерирует имя файла по стандартному формату
// name="ODataAutoConfig", version="1.0.5" → "ODataAutoConfig_v1.0.5.cfe"
func GenerateFileName(name, versionStr string) string {
	return fmt.Sprintf("%s_v%s.cfe", name, versionStr)
}

// ValidateFileName проверяет что имя файла соответствует формату и правилам безопасности
func ValidateFileName(fileName string) error {
	// Проверка на path traversal атаки
	if strings.Contains(fileName, "..") || strings.Contains(fileName, "/") || strings.Contains(fileName, "\\") {
		return fmt.Errorf("invalid file name: path traversal attempt detected")
	}

	// Проверка расширения
	if !strings.HasSuffix(fileName, ".cfe") {
		return fmt.Errorf("invalid file extension: must be .cfe")
	}

	// Проверка формата (попытка парсинга)
	_, _, err := ParseVersion(fileName)
	if err != nil {
		return fmt.Errorf("invalid file name format: %w", err)
	}

	return nil
}

// SanitizeFileName очищает имя файла от опасных символов
// Используется при авто-генерации имени из multipart upload
func SanitizeFileName(fileName string) string {
	// Берем только базовое имя (без пути)
	fileName = filepath.Base(fileName)

	// Удаляем опасные символы
	fileName = strings.ReplaceAll(fileName, "..", "")
	fileName = strings.ReplaceAll(fileName, "/", "")
	fileName = strings.ReplaceAll(fileName, "\\", "")

	return fileName
}
