package v8executor

import (
	"bytes"
	"fmt"
	"io"
	"os/exec"
	"strings"
	"sync"
	"time"

	"go.uber.org/zap"
)

// V8Executor handles execution of 1cv8.exe commands
// Uses async pipes to prevent subprocess deadlock
type V8Executor struct {
	exe1cv8Path    string
	defaultTimeout time.Duration
	logger         *zap.Logger
}

// NewV8Executor creates new V8Executor instance
func NewV8Executor(exe1cv8Path string, defaultTimeout time.Duration, logger *zap.Logger) *V8Executor {
	return &V8Executor{
		exe1cv8Path:    exe1cv8Path,
		defaultTimeout: defaultTimeout,
		logger:         logger,
	}
}

// Execute runs 1cv8.exe with given arguments
// Uses async pipes to prevent deadlock (IMPORTANT!)
// Returns stdout, stderr, and error
func (e *V8Executor) Execute(args []string) (string, string, error) {
	return e.ExecuteWithTimeout(args, e.defaultTimeout)
}

// ExecuteWithTimeout runs 1cv8.exe with custom timeout
func (e *V8Executor) ExecuteWithTimeout(args []string, timeout time.Duration) (string, string, error) {
	e.logger.Debug("executing 1cv8.exe command",
		zap.String("exe", e.exe1cv8Path),
		zap.Strings("args", sanitizeForLog(args)),
		zap.Duration("timeout", timeout))

	cmd := exec.Command(e.exe1cv8Path, args...)

	// Create async pipes to prevent deadlock
	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		return "", "", fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		return "", "", fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	// Start command
	if err := cmd.Start(); err != nil {
		return "", "", fmt.Errorf("failed to start command: %w", err)
	}

	// Async read from pipes
	var stdout, stderr bytes.Buffer
	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		io.Copy(&stdout, stdoutPipe)
	}()

	go func() {
		defer wg.Done()
		io.Copy(&stderr, stderrPipe)
	}()

	// Wait for pipes to finish reading
	wg.Wait()

	// Wait for command completion with timeout
	done := make(chan error, 1)
	go func() {
		done <- cmd.Wait()
	}()

	select {
	case <-time.After(timeout):
		cmd.Process.Kill()
		return stdout.String(), stderr.String(), fmt.Errorf("command timeout after %v", timeout)
	case err := <-done:
		stdoutStr := stdout.String()
		stderrStr := stderr.String()

		if err != nil {
			e.logger.Error("1cv8.exe command failed",
				zap.Error(err),
				zap.String("stderr", stderrStr))
			return stdoutStr, stderrStr, fmt.Errorf("command failed: %w", err)
		}

		e.logger.Debug("1cv8.exe command completed successfully")
		return stdoutStr, stderrStr, nil
	}
}

// CreateInfobase creates new file-based infobase
// Command: 1cv8.exe CREATEINFOBASE File=<path>
func (e *V8Executor) CreateInfobase(dbPath string) error {
	e.logger.Info("creating temporary infobase", zap.String("path", dbPath))

	args := []string{
		"CREATEINFOBASE",
		fmt.Sprintf("File=%s", dbPath),
	}

	stdout, stderr, err := e.Execute(args)
	if err != nil {
		return fmt.Errorf("failed to create infobase: %w (stderr: %s)", err, stderr)
	}

	e.logger.Debug("infobase created",
		zap.String("path", dbPath),
		zap.String("stdout", stdout))

	return nil
}

// LoadExtension loads .cfe extension into infobase
// Command: 1cv8.exe DESIGNER /F <db> /LoadCfg <cfePath> -Extension <extName>
func (e *V8Executor) LoadExtension(dbPath, cfePath, extName string) error {
	e.logger.Info("loading extension into infobase",
		zap.String("db", dbPath),
		zap.String("cfe", cfePath),
		zap.String("extension", extName))

	args := []string{
		"DESIGNER",
		fmt.Sprintf("/F%s", dbPath),
		fmt.Sprintf("/LoadCfg%s", cfePath),
		"-Extension", extName,
	}

	stdout, stderr, err := e.Execute(args)
	if err != nil {
		return fmt.Errorf("failed to load extension: %w (stderr: %s)", err, stderr)
	}

	e.logger.Debug("extension loaded",
		zap.String("extension", extName),
		zap.String("stdout", stdout))

	return nil
}

// DumpExtensionToXML dumps extension configuration to XML files
// Command: 1cv8.exe DESIGNER /F <db> /DumpConfigToFiles <xmlDir> -Extension <extName> -format Hierarchical
func (e *V8Executor) DumpExtensionToXML(dbPath, xmlDir, extName string) error {
	e.logger.Info("dumping extension to XML",
		zap.String("db", dbPath),
		zap.String("xmlDir", xmlDir),
		zap.String("extension", extName))

	args := []string{
		"DESIGNER",
		fmt.Sprintf("/F%s", dbPath),
		fmt.Sprintf("/DumpConfigToFiles%s", xmlDir),
		"-Extension", extName,
		"-format", "Hierarchical",
	}

	// DumpConfigToFiles can take 30-60 seconds for large extensions
	// Use extended timeout (5 minutes default)
	stdout, stderr, err := e.ExecuteWithTimeout(args, e.defaultTimeout)
	if err != nil {
		return fmt.Errorf("failed to dump extension to XML: %w (stderr: %s)", err, stderr)
	}

	e.logger.Debug("extension dumped to XML",
		zap.String("xmlDir", xmlDir),
		zap.String("stdout", stdout))

	return nil
}

// DeleteExtension removes extension from infobase
// Command: 1cv8.exe DESIGNER /F <db> /ConfigurationExtensionDelete -Extension <extName>
func (e *V8Executor) DeleteExtension(dbPath, extName string) error {
	e.logger.Info("deleting extension from infobase",
		zap.String("db", dbPath),
		zap.String("extension", extName))

	args := []string{
		"DESIGNER",
		fmt.Sprintf("/F%s", dbPath),
		"/ConfigurationExtensionDelete",
		"-Extension", extName,
	}

	stdout, stderr, err := e.Execute(args)
	if err != nil {
		// Non-critical error, just log it
		e.logger.Warn("failed to delete extension (non-critical)",
			zap.String("extension", extName),
			zap.Error(err),
			zap.String("stderr", stderr))
		return nil // Don't fail cleanup
	}

	e.logger.Debug("extension deleted",
		zap.String("extension", extName),
		zap.String("stdout", stdout))

	return nil
}

// buildConnectionString builds 1C connection string from components
// Format: /S<server>\<infobase> or /F<path>
func buildConnectionString(server, infobase, dbPath string) string {
	if server != "" && infobase != "" {
		// Server infobase
		return fmt.Sprintf("/S%s\\%s", server, infobase)
	}
	// File infobase
	return fmt.Sprintf("/F%s", dbPath)
}

// buildCredentials builds credential arguments
func buildCredentials(username, password string) []string {
	if username == "" {
		return []string{}
	}

	args := []string{fmt.Sprintf("/N%s", username)}
	if password != "" {
		args = append(args, fmt.Sprintf("/P%s", password))
	}

	return args
}

// DumpExtension dumps extension configuration to .cfe file
// Command: 1cv8.exe DESIGNER /F <db> /N <user> /P <pass> /DumpCfg <output.cfe> -Extension <extName>
// Used for creating backups before installation
func (e *V8Executor) DumpExtension(dbPath, username, password, extName, outputPath string) error {
	e.logger.Info("dumping extension to file",
		zap.String("db", dbPath),
		zap.String("extension", extName),
		zap.String("output", outputPath))

	args := []string{
		"DESIGNER",
		fmt.Sprintf("/F%s", dbPath),
	}

	// Add credentials
	args = append(args, buildCredentials(username, password)...)

	// Add dump command
	args = append(args,
		fmt.Sprintf("/DumpCfg%s", outputPath),
		"-Extension", extName,
	)

	stdout, stderr, err := e.Execute(args)
	if err != nil {
		return fmt.Errorf("failed to dump extension: %w (stderr: %s)", err, stderr)
	}

	e.logger.Debug("extension dumped successfully",
		zap.String("output", outputPath),
		zap.String("stdout", stdout))

	return nil
}

// UpdateExtensionDBConfig updates extension database configuration
// Command: 1cv8.exe DESIGNER /F <db> /N <user> /P <pass> /UpdateDBCfg -Extension <extName>
// Used after loading extension to apply changes to database
func (e *V8Executor) UpdateExtensionDBConfig(dbPath, username, password, extName string) error {
	e.logger.Info("updating extension DB config",
		zap.String("db", dbPath),
		zap.String("extension", extName))

	args := []string{
		"DESIGNER",
		fmt.Sprintf("/F%s", dbPath),
	}

	// Add credentials
	args = append(args, buildCredentials(username, password)...)

	// Add update command
	args = append(args,
		"/UpdateDBCfg",
		"-Extension", extName,
	)

	stdout, stderr, err := e.Execute(args)
	if err != nil {
		return fmt.Errorf("failed to update DB config: %w (stderr: %s)", err, stderr)
	}

	e.logger.Debug("extension DB config updated successfully",
		zap.String("stdout", stdout))

	return nil
}

// LoadExtensionFromFile loads extension from .cfe file into infobase
// Command: 1cv8.exe DESIGNER /F <db> /N <user> /P <pass> /LoadCfg <cfePath> -Extension <extName>
// Used for restoring from backup
func (e *V8Executor) LoadExtensionFromFile(dbPath, username, password, extName, cfePath string) error {
	e.logger.Info("loading extension from file",
		zap.String("db", dbPath),
		zap.String("cfe", cfePath),
		zap.String("extension", extName))

	args := []string{
		"DESIGNER",
		fmt.Sprintf("/F%s", dbPath),
	}

	// Add credentials
	args = append(args, buildCredentials(username, password)...)

	// Add load command
	args = append(args,
		fmt.Sprintf("/LoadCfg%s", cfePath),
		"-Extension", extName,
	)

	stdout, stderr, err := e.Execute(args)
	if err != nil {
		return fmt.Errorf("failed to load extension: %w (stderr: %s)", err, stderr)
	}

	e.logger.Debug("extension loaded from file",
		zap.String("extension", extName),
		zap.String("stdout", stdout))

	return nil
}

// sanitizeForLog removes sensitive information from command arguments
func sanitizeForLog(args []string) []string {
	sanitized := make([]string, len(args))
	for i, arg := range args {
		if strings.HasPrefix(arg, "/P") {
			sanitized[i] = "/P***"
		} else {
			sanitized[i] = arg
		}
	}
	return sanitized
}
