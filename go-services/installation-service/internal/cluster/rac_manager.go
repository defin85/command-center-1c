package cluster

import (
	"context"
	"fmt"
	"os/exec"
	"time"

	"golang.org/x/sync/errgroup"
	"golang.org/x/sync/semaphore"
)

// RACManager implements ClusterManager using RAC CLI
type RACManager struct {
	racPath     string
	serverAddr  string
	clusterUser string
	clusterPwd  string
	timeout     time.Duration
}

// NewRACManager creates a new RAC manager instance
func NewRACManager(racPath, serverAddr, clusterUser, clusterPwd string, timeout time.Duration) *RACManager {
	return &RACManager{
		racPath:     racPath,
		serverAddr:  serverAddr,
		clusterUser: clusterUser,
		clusterPwd:  clusterPwd,
		timeout:     timeout,
	}
}

// GetClusterInfo retrieves information about the 1C cluster
func (m *RACManager) GetClusterInfo(ctx context.Context) (*ClusterInfo, error) {
	// Create command context with timeout
	cmdCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	// Build command: rac <server> cluster list
	args := []string{m.serverAddr, "cluster", "list"}
	cmd := exec.CommandContext(cmdCtx, m.racPath, args...)

	// Execute command
	output, err := cmd.CombinedOutput()
	if err != nil {
		if cmdCtx.Err() == context.DeadlineExceeded {
			return nil, fmt.Errorf("cluster list command timeout")
		}
		return nil, fmt.Errorf("failed to execute cluster list: %w (output: %s)", err, string(output))
	}

	// Parse output
	cluster, err := parseClusterInfo(output)
	if err != nil {
		return nil, fmt.Errorf("failed to parse cluster info: %w", err)
	}

	return cluster, nil
}

// GetInfobaseList retrieves the list of infobases in the cluster
func (m *RACManager) GetInfobaseList(ctx context.Context, detailed bool) ([]InfobaseInfo, error) {
	// First, get cluster UUID
	cluster, err := m.GetClusterInfo(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get cluster info: %w", err)
	}

	// Get summary list (fast)
	summaryList, err := m.getInfobaseSummaryList(ctx, cluster.UUID)
	if err != nil {
		return nil, fmt.Errorf("failed to get infobase summary list: %w", err)
	}

	// If detailed info not requested, return summary
	if !detailed {
		return summaryList, nil
	}

	// Enrich with details (slow)
	detailedList, err := m.enrichWithDetails(ctx, cluster.UUID, summaryList)
	if err != nil {
		return nil, fmt.Errorf("failed to enrich with details: %w", err)
	}

	return detailedList, nil
}

// getInfobaseSummaryList gets summary list of infobases (fast)
func (m *RACManager) getInfobaseSummaryList(ctx context.Context, clusterUUID string) ([]InfobaseInfo, error) {
	// Create command context with timeout
	cmdCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	// Build command: rac <server> infobase summary list --cluster=<uuid>
	args := []string{
		m.serverAddr,
		"infobase",
		"summary",
		"list",
		fmt.Sprintf("--cluster=%s", clusterUUID),
	}

	// Add cluster credentials if provided
	if m.clusterUser != "" {
		args = append(args, fmt.Sprintf("--cluster-user=%s", m.clusterUser))
	}
	if m.clusterPwd != "" {
		args = append(args, fmt.Sprintf("--cluster-pwd=%s", m.clusterPwd))
	}

	cmd := exec.CommandContext(cmdCtx, m.racPath, args...)

	// Execute command
	output, err := cmd.CombinedOutput()
	if err != nil {
		if cmdCtx.Err() == context.DeadlineExceeded {
			return nil, fmt.Errorf("infobase summary list command timeout")
		}
		return nil, fmt.Errorf("failed to execute infobase summary list: %w (output: %s)", err, string(output))
	}

	// Parse output
	infobases, err := parseInfobaseSummaryList(output)
	if err != nil {
		return nil, fmt.Errorf("failed to parse infobase summary list: %w", err)
	}

	return infobases, nil
}

// enrichWithDetails fetches detailed info for each infobase using worker pool (parallel)
func (m *RACManager) enrichWithDetails(ctx context.Context, clusterUUID string, summaryList []InfobaseInfo) ([]InfobaseInfo, error) {
	// Create semaphore to limit concurrent workers
	const maxWorkers = 10
	sem := semaphore.NewWeighted(maxWorkers)

	// Use errgroup for error handling and coordination
	g, gctx := errgroup.WithContext(ctx)

	// Result slice (pre-allocated)
	results := make([]InfobaseInfo, len(summaryList))

	// Launch workers
	for i, summary := range summaryList {
		i, summary := i, summary // capture loop variables

		// Acquire semaphore
		if err := sem.Acquire(ctx, 1); err != nil {
			return nil, fmt.Errorf("failed to acquire semaphore: %w", err)
		}

		// Launch goroutine
		g.Go(func() error {
			defer sem.Release(1) // Always release

			// Check context cancellation
			if gctx.Err() != nil {
				return gctx.Err()
			}

			// Get detailed info
			details, err := m.getInfobaseDetails(gctx, clusterUUID, summary.UUID)
			if err != nil {
				// Log error but don't fail - use summary data
				// In production, use proper logging here
				results[i] = summary
				return nil // Continue with other infobases
			}

			// Merge and store
			results[i] = mergeInfobaseDetails(summary, details)
			return nil
		})
	}

	// Wait for all workers to complete
	if err := g.Wait(); err != nil {
		return nil, fmt.Errorf("worker pool error: %w", err)
	}

	return results, nil
}

// getInfobaseDetails gets detailed info for a single infobase
func (m *RACManager) getInfobaseDetails(ctx context.Context, clusterUUID, infobaseUUID string) (InfobaseInfo, error) {
	// Create command context with timeout
	cmdCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	// Build command: rac <server> infobase info --cluster=<uuid> --infobase=<uuid>
	args := []string{
		m.serverAddr,
		"infobase",
		"info",
		fmt.Sprintf("--cluster=%s", clusterUUID),
		fmt.Sprintf("--infobase=%s", infobaseUUID),
	}

	// Add cluster credentials if provided
	if m.clusterUser != "" {
		args = append(args, fmt.Sprintf("--cluster-user=%s", m.clusterUser))
	}
	if m.clusterPwd != "" {
		args = append(args, fmt.Sprintf("--cluster-pwd=%s", m.clusterPwd))
	}

	cmd := exec.CommandContext(cmdCtx, m.racPath, args...)

	// Execute command
	output, err := cmd.CombinedOutput()
	if err != nil {
		if cmdCtx.Err() == context.DeadlineExceeded {
			return InfobaseInfo{}, fmt.Errorf("infobase info command timeout")
		}
		return InfobaseInfo{}, fmt.Errorf("failed to execute infobase info: %w (output: %s)", err, string(output))
	}

	// Parse output
	infobase, err := parseInfobaseDetails(output)
	if err != nil {
		return InfobaseInfo{}, fmt.Errorf("failed to parse infobase details: %w", err)
	}

	return infobase, nil
}

// Close releases any resources held by the manager
func (m *RACManager) Close() error {
	// No resources to release for RAC CLI
	return nil
}
