package service

import (
	"bytes"
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/command-center-1c/batch-service/pkg/v8errors"
)

// ExtensionLister handles listing of 1C extensions
type ExtensionLister struct {
	exe1cv8Path string
	timeout     time.Duration
}

// NewExtensionLister creates a new ExtensionLister
func NewExtensionLister(exe1cv8Path string, timeout time.Duration) *ExtensionLister {
	if exe1cv8Path == "" {
		exe1cv8Path = `C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe`
	}

	if timeout == 0 {
		timeout = 5 * time.Minute
	}

	return &ExtensionLister{
		exe1cv8Path: exe1cv8Path,
		timeout:     timeout,
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
	ctx, cancel := context.WithTimeout(ctx, l.timeout)
	defer cancel()

	// Create temporary file for report
	tmpFile := filepath.Join(os.TempDir(), fmt.Sprintf("extensions_report_%d.txt", time.Now().Unix()))
	defer os.Remove(tmpFile) // Clean up

	// Build command: 1cv8.exe DESIGNER /F server\infobase /N user /P pass /ConfigurationRepositoryReport tmpFile
	cmd := exec.CommandContext(ctx,
		l.exe1cv8Path,
		"DESIGNER",
		"/F", fmt.Sprintf("%s\\%s", req.Server, req.InfobaseName),
		"/N", req.Username,
		"/P", req.Password,
		"/ConfigurationRepositoryReport", tmpFile,
	)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		return nil, v8errors.ParseV8Error(stdout.String(), stderr.String(), err)
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
