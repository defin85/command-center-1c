package orchestrator

import (
	"context"
	"fmt"
	"net/url"
)

type ArtifactPurgeJobClaimRequest struct {
	WorkerInstance string `json:"worker_instance,omitempty"`
}

type ArtifactPurgeJobClaim struct {
	JobID        string   `json:"job_id"`
	ArtifactID   string   `json:"artifact_id"`
	Mode         string   `json:"mode"`
	Status       string   `json:"status"`
	Prefix       string   `json:"prefix"`
	StorageKeys  []string `json:"storage_keys"`
	TotalObjects int      `json:"total_objects"`
	TotalBytes   int64    `json:"total_bytes"`
}

type ArtifactPurgeJobClaimResponse struct {
	Success bool                   `json:"success"`
	Job     *ArtifactPurgeJobClaim `json:"job"`
}

type ArtifactPurgeJobProgressUpdateRequest struct {
	DeletedObjects int   `json:"deleted_objects,omitempty"`
	DeletedBytes   int64 `json:"deleted_bytes,omitempty"`
}

type ArtifactPurgeJobCompleteRequest struct {
	Status         string `json:"status"`
	DeletedObjects int    `json:"deleted_objects,omitempty"`
	DeletedBytes   int64  `json:"deleted_bytes,omitempty"`
	ErrorCode      string `json:"error_code,omitempty"`
	ErrorMessage   string `json:"error_message,omitempty"`
}

func (c *Client) ClaimArtifactPurgeJob(ctx context.Context, workerInstance string) (*ArtifactPurgeJobClaim, error) {
	req := ArtifactPurgeJobClaimRequest{WorkerInstance: workerInstance}
	var resp ArtifactPurgeJobClaimResponse
	if err := c.post(ctx, "/api/v2/internal/artifacts/claim-purge-job", req, &resp); err != nil {
		return nil, err
	}
	if !resp.Success {
		return nil, fmt.Errorf("claim purge job failed")
	}
	return resp.Job, nil
}

func (c *Client) UpdateArtifactPurgeJob(ctx context.Context, jobID string, deletedObjects int, deletedBytes int64) error {
	path := "/api/v2/internal/artifacts/update-purge-job?job_id=" + url.QueryEscape(jobID)
	req := ArtifactPurgeJobProgressUpdateRequest{
		DeletedObjects: deletedObjects,
		DeletedBytes:   deletedBytes,
	}
	return c.post(ctx, path, req, nil)
}

func (c *Client) CompleteArtifactPurgeJob(
	ctx context.Context,
	jobID string,
	status string,
	deletedObjects int,
	deletedBytes int64,
	errorCode string,
	errorMessage string,
) error {
	path := "/api/v2/internal/artifacts/complete-purge-job?job_id=" + url.QueryEscape(jobID)
	req := ArtifactPurgeJobCompleteRequest{
		Status:         status,
		DeletedObjects: deletedObjects,
		DeletedBytes:   deletedBytes,
		ErrorCode:      errorCode,
		ErrorMessage:   errorMessage,
	}
	return c.post(ctx, path, req, nil)
}
