package service

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// FileValidator validates extension files before operations
type FileValidator struct{}

// NewFileValidator creates a new FileValidator
func NewFileValidator() *FileValidator {
	return &FileValidator{}
}

// ValidateExtensionFile validates a .cfe file path
func (v *FileValidator) ValidateExtensionFile(path string) error {
	// 1. Sanitize path (prevent path traversal)
	clean := filepath.Clean(path)
	if strings.Contains(clean, "..") {
		return errors.New("invalid path: contains '..' (path traversal detected)")
	}

	// 2. Check extension
	if !strings.HasSuffix(strings.ToLower(clean), ".cfe") {
		return errors.New("invalid file extension (must be .cfe)")
	}

	// 3. Check file exists and readable
	info, err := os.Stat(clean)
	if err != nil {
		if os.IsNotExist(err) {
			return fmt.Errorf("file not found: %s", clean)
		}
		return fmt.Errorf("cannot access file: %w", err)
	}

	// 4. Check it's a regular file, not directory (BEFORE size check)
	if info.IsDir() {
		return errors.New("path is a directory, not a file")
	}

	// 5. Check file size (> 0, < 100MB reasonable limit)
	if info.Size() == 0 {
		return errors.New("file is empty")
	}
	maxSize := int64(100 * 1024 * 1024) // 100 MB
	if info.Size() > maxSize {
		return fmt.Errorf("file too large (max 100MB, got %d bytes)", info.Size())
	}

	return nil
}
