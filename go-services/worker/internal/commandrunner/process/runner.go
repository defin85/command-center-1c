package process

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

const (
	defaultStdoutMaxBytes = 1 << 20 // 1 MiB
	defaultStderrMaxBytes = 1 << 20 // 1 MiB
	defaultWaitDelay      = 2 * time.Second
)

type Spec struct {
	ExePath string
	Args    []string
	Stdin   string

	Timeout        time.Duration
	WaitDelay      time.Duration
	StdoutMaxBytes int
	StderrMaxBytes int
}

type Result struct {
	Stdout string
	Stderr string

	ExitCode int
	Duration time.Duration

	StdoutTruncated bool
	StderrTruncated bool
	WaitDelayHit    bool
}

type tailBuffer struct {
	max       int
	buf       []byte
	truncated bool
}

func newTailBuffer(max int) *tailBuffer {
	if max < 0 {
		max = 0
	}
	return &tailBuffer{max: max}
}

func (b *tailBuffer) Write(p []byte) (int, error) {
	if b.max == 0 {
		if len(p) > 0 {
			b.truncated = true
		}
		return len(p), nil
	}
	if len(p) >= b.max {
		b.buf = append(b.buf[:0], p[len(p)-b.max:]...)
		b.truncated = true
		return len(p), nil
	}
	if len(b.buf)+len(p) <= b.max {
		b.buf = append(b.buf, p...)
		return len(p), nil
	}
	overflow := len(b.buf) + len(p) - b.max
	if overflow > len(b.buf) {
		overflow = len(b.buf)
	}
	b.buf = append(b.buf[overflow:], p...)
	b.truncated = true
	return len(p), nil
}

func (b *tailBuffer) String() string { return string(b.buf) }

func (b *tailBuffer) Truncated() bool { return b.truncated }

func parseIntEnv(name string, def int) int {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return def
	}
	parsed, err := strconv.Atoi(raw)
	if err != nil || parsed < 0 {
		return def
	}
	return parsed
}

func parseDurationEnv(name string, def time.Duration) time.Duration {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return def
	}
	parsed, err := time.ParseDuration(raw)
	if err != nil || parsed < 0 {
		return def
	}
	return parsed
}

func Run(ctxContext context.Context, spec Spec) (*Result, error) {
	startTime := time.Now()
	result := &Result{ExitCode: -1}

	if strings.TrimSpace(spec.ExePath) == "" {
		result.Duration = time.Since(startTime)
		return result, fmt.Errorf("executable path is not configured")
	}

	info, statErr := os.Stat(spec.ExePath)
	if statErr != nil {
		result.Duration = time.Since(startTime)
		if os.IsNotExist(statErr) {
			return result, fmt.Errorf("executable not found at path: %s", spec.ExePath)
		}
		return result, fmt.Errorf("failed to stat executable at path %s: %w", spec.ExePath, statErr)
	}
	if info.IsDir() {
		result.Duration = time.Since(startTime)
		return result, fmt.Errorf("executable path points to a directory: %s", spec.ExePath)
	}

	stdoutMax := spec.StdoutMaxBytes
	if stdoutMax <= 0 {
		stdoutMax = parseIntEnv("COMMANDRUNNER_STDOUT_MAX_BYTES", defaultStdoutMaxBytes)
	}
	stderrMax := spec.StderrMaxBytes
	if stderrMax <= 0 {
		stderrMax = parseIntEnv("COMMANDRUNNER_STDERR_MAX_BYTES", defaultStderrMaxBytes)
	}
	waitDelay := spec.WaitDelay
	if waitDelay == 0 {
		waitDelay = parseDurationEnv("COMMANDRUNNER_WAIT_DELAY", defaultWaitDelay)
	}

	ctx := ctxContext
	if spec.Timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctxContext, spec.Timeout)
		defer cancel()
	}

	stdoutBuf := newTailBuffer(stdoutMax)
	stderrBuf := newTailBuffer(stderrMax)

	cmd := exec.CommandContext(ctx, spec.ExePath, spec.Args...)
	cmd.Stdout = stdoutBuf
	cmd.Stderr = stderrBuf
	if spec.Stdin != "" {
		cmd.Stdin = strings.NewReader(spec.Stdin)
	}
	cmd.WaitDelay = waitDelay

	runErr := cmd.Run()
	duration := time.Since(startTime)

	result.Stdout = stdoutBuf.String()
	result.Stderr = stderrBuf.String()
	result.StdoutTruncated = stdoutBuf.Truncated()
	result.StderrTruncated = stderrBuf.Truncated()
	result.Duration = duration

	if cmd.ProcessState != nil {
		result.ExitCode = cmd.ProcessState.ExitCode()
	}

	if errors.Is(runErr, exec.ErrWaitDelay) {
		result.WaitDelayHit = true
		if result.ExitCode == 0 && ctx.Err() == nil {
			return result, nil
		}
	}

	if ctx.Err() != nil {
		return result, fmt.Errorf("operation cancelled: %w", ctx.Err())
	}

	return result, runErr
}
