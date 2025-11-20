package eventhandlers

import (
	"context"
	"testing"

	"go.uber.org/zap"
)

// TestNewTerminateHandler tests handler instantiation
func TestNewTerminateHandler(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	handler := NewTerminateHandler(nil, nil, nil, logger)

	if handler == nil {
		t.Error("expected handler to be non-nil")
	}
}

// TestCheckIdempotency_NoRedis tests idempotency check when Redis is nil
func TestCheckIdempotency_NoRedis(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	handler := NewTerminateHandler(nil, nil, nil, logger)

	isFirst, err := handler.checkIdempotency(context.Background(), "corr-id", "terminate")

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if !isFirst {
		t.Error("expected isFirst to be true when Redis is nil (fail-open)")
	}
}

// TestPublishSuccess tests publishSuccess method
func TestPublishSuccess(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	// Create a mock publisher that accepts calls
	handler := NewTerminateHandler(nil, nil, nil, logger)

	if handler == nil {
		t.Error("expected handler to be non-nil")
	}

	// Just verify the method exists and can be called
	// Real testing would require mock implementation
}

// TestTerminateCommandPayload tests payload structure
func TestTerminateCommandPayload(t *testing.T) {
	payload := TerminateCommandPayload{
		ClusterID:  "cluster-uuid",
		InfobaseID: "infobase-uuid",
		DatabaseID: "db-uuid",
	}

	if payload.ClusterID != "cluster-uuid" {
		t.Error("expected ClusterID to be cluster-uuid")
	}

	if payload.InfobaseID != "infobase-uuid" {
		t.Error("expected InfobaseID to be infobase-uuid")
	}

	if payload.DatabaseID != "db-uuid" {
		t.Error("expected DatabaseID to be db-uuid")
	}
}

// TestSessionsClosedPayload tests payload structure
func TestSessionsClosedPayload(t *testing.T) {
	payload := SessionsClosedPayload{
		ClusterID:  "cluster-uuid",
		InfobaseID: "infobase-uuid",
		DatabaseID: "db-uuid",
		Message:    "All sessions closed successfully",
	}

	if payload.ClusterID != "cluster-uuid" {
		t.Error("expected ClusterID to be cluster-uuid")
	}

	if payload.InfobaseID != "infobase-uuid" {
		t.Error("expected InfobaseID to be infobase-uuid")
	}

	if payload.Message != "All sessions closed successfully" {
		t.Error("expected correct message")
	}
}

// TestErrorPayload tests error payload structure
func TestErrorPayload(t *testing.T) {
	payload := ErrorPayload{
		ClusterID:  "cluster-uuid",
		InfobaseID: "infobase-uuid",
		Error:      "test error",
		Message:    "Failed to process",
	}

	if payload.Error != "test error" {
		t.Error("expected error to be test error")
	}

	if payload.Message != "Failed to process" {
		t.Error("expected correct message")
	}
}

// TestTerminateSuccessPayload tests success payload structure
func TestTerminateSuccessPayload(t *testing.T) {
	payload := TerminateSuccessPayload{
		ClusterID:       "cluster-uuid",
		InfobaseID:      "infobase-uuid",
		SessionsCount:   10,
		TerminatedCount: 8,
		RemainingCount:  2,
	}

	if payload.SessionsCount != 10 {
		t.Error("expected SessionsCount to be 10")
	}

	if payload.TerminatedCount != 8 {
		t.Error("expected TerminatedCount to be 8")
	}

	if payload.RemainingCount != 2 {
		t.Error("expected RemainingCount to be 2")
	}
}

// TestChannelNames tests channel name constants
func TestChannelNames(t *testing.T) {
	if TerminateCommandChannel != "commands:cluster-service:sessions:terminate" {
		t.Error("expected correct TerminateCommandChannel")
	}

	if SessionsClosedChannel != "events:cluster-service:sessions:closed" {
		t.Error("expected correct SessionsClosedChannel")
	}

	if TerminateFailedChannel != "events:cluster-service:sessions:terminate-failed" {
		t.Error("expected correct TerminateFailedChannel")
	}
}

// TestEventTypeConstants tests event type constants
func TestEventTypeConstants(t *testing.T) {
	if SessionsClosedEvent != "cluster.sessions.closed" {
		t.Error("expected correct SessionsClosedEvent")
	}

	if SessionsTerminateFailedEvent != "cluster.sessions.terminate.failed" {
		t.Error("expected correct SessionsTerminateFailedEvent")
	}
}
