package service

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"time"

	"github.com/command-center-1c/batch-service/pkg/v8errors"
)

// ExtensionDeleter handles deletion of 1C extensions
type ExtensionDeleter struct {
	exe1cv8Path string
	timeout     time.Duration
}

// NewExtensionDeleter creates a new ExtensionDeleter
func NewExtensionDeleter(exe1cv8Path string, timeout time.Duration) *ExtensionDeleter {
	if exe1cv8Path == "" {
		exe1cv8Path = `C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe`
	}

	if timeout == 0 {
		timeout = 5 * time.Minute
	}

	return &ExtensionDeleter{
		exe1cv8Path: exe1cv8Path,
		timeout:     timeout,
	}
}

// DeleteRequest contains parameters for extension deletion
type DeleteRequest struct {
	Server        string
	InfobaseName  string
	Username      string
	Password      string
	ExtensionName string
}

// DeleteExtension deletes an extension from a 1C infobase
func (d *ExtensionDeleter) DeleteExtension(ctx context.Context, req DeleteRequest) error {
	ctx, cancel := context.WithTimeout(ctx, d.timeout)
	defer cancel()

	// Build command: 1cv8.exe DESIGNER /F server\infobase /N user /P pass /DeleteCfg -Extension name
	cmd := exec.CommandContext(ctx,
		d.exe1cv8Path,
		"DESIGNER",
		"/F", fmt.Sprintf("%s\\%s", req.Server, req.InfobaseName),
		"/N", req.Username,
		"/P", req.Password,
		"/DeleteCfg",
		"-Extension", req.ExtensionName,
	)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		// Parse V8 error from stdout/stderr
		return v8errors.ParseV8Error(stdout.String(), stderr.String(), err)
	}

	return nil
}
