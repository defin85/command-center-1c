package onec

// Package onec provides 1C platform integration for extension installation.

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"regexp"
	"strings"
	"time"

	"github.com/rs/zerolog/log"

	"github.com/commandcenter1c/commandcenter/installation-service/internal/config"
)

// Installer handles 1C extension installation via 1cv8.exe
type Installer struct {
	config *config.OneCConfig
}

// InstallRequest contains all parameters needed for installation
type InstallRequest struct {
	TaskID           string
	DatabaseID       int
	DatabaseName     string
	ConnectionString string
	Username         string
	Password         string
	ExtensionPath    string
	ExtensionName    string
}

// NewInstaller creates a new 1C installer
func NewInstaller(cfg *config.OneCConfig) *Installer {
	return &Installer{config: cfg}
}

// validateConnectionString validates the connection string to prevent command injection
func validateConnectionString(connStr string) error {
	// Connection string должен иметь формат: /S"server\database"
	// Запретить опасные символы
	dangerous := []string{";", "&", "|", ">", "<", "`", "$", "(", ")", "{", "}"}
	for _, char := range dangerous {
		if strings.Contains(connStr, char) {
			return fmt.Errorf("connection string contains dangerous character: %s", char)
		}
	}

	// Проверить формат
	matched, _ := regexp.MatchString(`^/S"[^"]+\\[^"]+"$`, connStr)
	if !matched {
		return fmt.Errorf("invalid connection string format: %s", connStr)
	}

	return nil
}

// InstallExtension installs an extension to a 1C database
// Performs two operations:
// 1. LoadCfg - loads the extension CFE file
// 2. UpdateDBCfg - applies the extension to the database
func (i *Installer) InstallExtension(ctx context.Context, req InstallRequest) error {
	log.Info().
		Str("task_id", req.TaskID).
		Int("database_id", req.DatabaseID).
		Str("database_name", req.DatabaseName).
		Msg("Starting extension installation")

	// Step 1: LoadCfg - load extension from CFE file
	if err := i.loadExtension(ctx, req); err != nil {
		return fmt.Errorf("failed to load extension: %w", err)
	}

	// Step 2: UpdateDBCfg - apply extension to database
	if err := i.updateDBCfg(ctx, req); err != nil {
		return fmt.Errorf("failed to update DB config: %w", err)
	}

	log.Info().
		Str("task_id", req.TaskID).
		Str("database_name", req.DatabaseName).
		Msg("Extension installation completed successfully")

	return nil
}

// loadExtension loads the CFE file to the database
func (i *Installer) loadExtension(ctx context.Context, req InstallRequest) error {
	// Validate connection string before use
	if err := validateConnectionString(req.ConnectionString); err != nil {
		return fmt.Errorf("invalid connection string: %w", err)
	}

	args := []string{
		"CONFIG",
		fmt.Sprintf("/S%s", req.ConnectionString),
		fmt.Sprintf("/N%s", req.Username),
		fmt.Sprintf("/P%s", req.Password),
		"/LoadCfg", req.ExtensionPath,
		"-Extension", req.ExtensionName,
	}

	return i.executeCommand(ctx, args, "LoadCfg")
}

// updateDBCfg applies the extension to the database configuration
func (i *Installer) updateDBCfg(ctx context.Context, req InstallRequest) error {
	// Validate connection string before use
	if err := validateConnectionString(req.ConnectionString); err != nil {
		return fmt.Errorf("invalid connection string: %w", err)
	}

	args := []string{
		"CONFIG",
		fmt.Sprintf("/S%s", req.ConnectionString),
		fmt.Sprintf("/N%s", req.Username),
		fmt.Sprintf("/P%s", req.Password),
		"/UpdateDBCfg",
		"-Extension", req.ExtensionName,
	}

	return i.executeCommand(ctx, args, "UpdateDBCfg")
}

// executeCommand executes 1cv8.exe with given arguments and timeout
func (i *Installer) executeCommand(ctx context.Context, args []string, operation string) error {
	// Create context with timeout
	cmdCtx, cancel := context.WithTimeout(ctx, time.Duration(i.config.TimeoutSeconds)*time.Second)
	defer cancel()

	// Create command
	cmd := exec.CommandContext(cmdCtx, i.config.PlatformPath, args...)

	// Buffers for stdout/stderr
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// Log command (without password!)
	safeArgs := i.sanitizeArgs(args)
	log.Debug().
		Str("command", i.config.PlatformPath).
		Strs("args", safeArgs).
		Str("operation", operation).
		Msg("Executing 1cv8.exe")

	// Execute command
	startTime := time.Now()
	err := cmd.Run()
	duration := time.Since(startTime)

	// Get exit code
	exitCode := 0
	if cmd.ProcessState != nil {
		exitCode = cmd.ProcessState.ExitCode()
	}

	// Log result
	log.Info().
		Str("operation", operation).
		Dur("duration", duration).
		Int("exit_code", exitCode).
		Msg("Command executed")

	if err != nil {
		// Log stdout/stderr on error
		log.Error().
			Err(err).
			Str("operation", operation).
			Str("stdout", stdout.String()).
			Str("stderr", stderr.String()).
			Msg("Command failed")

		return fmt.Errorf("%s failed: %w", operation, err)
	}

	// Log stdout for debugging (DEBUG level)
	if stdout.Len() > 0 {
		log.Debug().
			Str("operation", operation).
			Str("stdout", stdout.String()).
			Msg("Command output")
	}

	return nil
}

// sanitizeArgs removes password from arguments for safe logging
func (i *Installer) sanitizeArgs(args []string) []string {
	safe := make([]string, len(args))
	copy(safe, args)

	for idx, arg := range safe {
		if strings.HasPrefix(arg, "/P") {
			safe[idx] = "/P****"
		}
	}

	return safe
}

// InstallExtensionWithRetry installs extension with retry mechanism
func (i *Installer) InstallExtensionWithRetry(ctx context.Context, req InstallRequest, maxRetries int, retryDelay time.Duration) error {
	var lastErr error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		err := i.InstallExtension(ctx, req)
		if err == nil {
			// Success
			return nil
		}

		lastErr = err
		log.Warn().
			Err(err).
			Int("attempt", attempt).
			Int("max_retries", maxRetries).
			Str("task_id", req.TaskID).
			Str("database_name", req.DatabaseName).
			Msg("Installation attempt failed, retrying...")

		if attempt < maxRetries {
			// Wait before next attempt with exponential backoff
			select {
			case <-time.After(retryDelay):
				// Continue to next attempt
				retryDelay *= 2 // Exponential backoff
			case <-ctx.Done():
				return ctx.Err()
			}
		}
	}

	return fmt.Errorf("installation failed after %d attempts: %w", maxRetries, lastErr)
}
