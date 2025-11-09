package service

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	"github.com/command-center-1c/batch-service/internal/infrastructure/v8executor"
	"github.com/command-center-1c/batch-service/pkg/v8errors"
)

// ExtensionLister handles listing of 1C extensions
type ExtensionLister struct {
	executor *v8executor.V8Executor
}

// NewExtensionLister creates a new ExtensionLister
func NewExtensionLister(exe1cv8Path string, timeout time.Duration) *ExtensionLister {
	executor := v8executor.NewV8Executor(exe1cv8Path, timeout)

	return &ExtensionLister{
		executor: executor,
	}
}

// ListRequest contains parameters for listing extensions
type ListRequest struct {
	Server       string
	InfobaseName string
	Username     string
	Password     string
}

// ExtensionInfo represents information about an extension
type ExtensionInfo struct {
	Name    string `json:"name"`
	Version string `json:"version,omitempty"`
}

// ListExtensions returns a list of extensions installed in the infobase
// NOTE: This is a simplified implementation using ConfigurationRepositoryReport
// The actual parsing depends on the report format which needs empirical testing
func (l *ExtensionLister) ListExtensions(ctx context.Context, req ListRequest) ([]ExtensionInfo, error) {
	// Create temporary file for report
	tmpFile := filepath.Join(os.TempDir(), fmt.Sprintf("extensions_report_%d.txt", time.Now().UnixNano()))

	// Ensure cleanup even on panic
	defer func() {
		if err := os.Remove(tmpFile); err != nil && !os.IsNotExist(err) {
			log.Printf("WARNING: Failed to cleanup temp file %s: %v", tmpFile, err)
		}
	}()

	// Build command arguments
	args := v8executor.BuildListCommand(
		req.Server,
		req.InfobaseName,
		req.Username,
		req.Password,
		tmpFile,
	)

	// Execute command using V8Executor with async stdout/stderr reading
	result, err := l.executor.Execute(ctx, args)
	if err != nil {
		// Parse V8 error from stdout/stderr
		stdout := ""
		stderr := ""
		if result != nil {
			stdout = result.Stdout
			stderr = result.Stderr
		}
		return nil, v8errors.ParseV8Error(stdout, stderr, err)
	}

	// Read report file
	content, err := os.ReadFile(tmpFile)
	if err != nil {
		return nil, fmt.Errorf("failed to read report file: %w", err)
	}

	// Parse extensions from report
	extensions := parseExtensionsFromReport(string(content))

	return extensions, nil
}

// parseExtensionsFromReport parses the ConfigurationRepositoryReport output
// TODO: This is a stub implementation - the actual format needs to be determined
// through empirical testing on a real 1C database
func parseExtensionsFromReport(content string) []ExtensionInfo {
	// WARNING: This is a placeholder implementation
	// The actual report format from ConfigurationRepositoryReport depends on:
	// - 1C platform version
	// - Locale (Russian/English)
	// - Report format changes between versions
	//
	// For production use, this needs to be tested with actual 1C databases
	// and the parsing logic adjusted accordingly.

	log.Println("WARNING: ListExtensions uses stub implementation")
	log.Println("ConfigurationRepositoryReport format needs empirical testing")
	log.Printf("Report content length: %d bytes", len(content))

	// Return empty list for now with a warning
	// In production, implement actual parsing logic based on real report format
	return []ExtensionInfo{}
}
