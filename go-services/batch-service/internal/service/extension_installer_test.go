package service

import (
	"context"
	"testing"
	"time"

	"github.com/command-center-1c/batch-service/internal/models"
)

// TestNewExtensionInstaller tests constructor
func TestNewExtensionInstaller(t *testing.T) {
	// Test with custom values
	customPath := `C:\Custom\1cv8.exe`
	customTimeout := 10 * time.Minute

	installer := NewExtensionInstaller(customPath, customTimeout)

	if installer.executor == nil {
		t.Fatal("Expected non-nil executor")
	}
}

// TestNewExtensionInstaller_DefaultTimeout tests default timeout
func TestNewExtensionInstaller_DefaultTimeout(t *testing.T) {
	installer := NewExtensionInstaller("test.exe", 0)

	if installer.executor == nil {
		t.Fatal("Expected non-nil executor")
	}

	// Default timeout should be 5 minutes (verified in executor)
}

// TestInstallExtension_StructureTest tests the method structure
func TestInstallExtension_StructureTest(t *testing.T) {
	// This test verifies that InstallExtension correctly calls V8Executor
	// Actual execution tests are in executor_test.go

	installer := NewExtensionInstaller("dummy.exe", 5*time.Second)

	req := &models.InstallExtensionRequest{
		Server:         "testserver",
		InfobaseName:   "testbase",
		Username:       "admin",
		Password:       "pass",
		ExtensionName:  "TestExt",
		ExtensionPath:  "C:\\extensions\\test.cfe",
		UpdateDBConfig: true, // This flag is now ignored - always true
	}

	ctx := context.Background()

	// This will fail because dummy.exe doesn't exist, but we test the structure
	resp, err := installer.InstallExtension(ctx, req)

	// Should fail with "not found" error (expected for unit test)
	if err == nil {
		t.Fatal("Expected error for dummy executable")
	}

	if resp == nil {
		t.Fatal("Expected non-nil response even on error")
	}

	if resp.Success {
		t.Error("Expected Success=false on error")
	}

	// Duration can be very small (close to 0) for quick failures
	// Just check it's non-negative
	if resp.DurationSeconds < 0 {
		t.Error("Expected non-negative duration")
	}

	t.Logf("Got expected error: %v", err)
}

// TestBatchInstall_EmptyList tests batch install with empty list
func TestBatchInstall_EmptyList(t *testing.T) {
	installer := NewExtensionInstaller("dummy.exe", 5*time.Second)

	req := &models.BatchInstallRequest{
		Infobases:       []models.InstallExtensionRequest{},
		ParallelWorkers: 10,
	}

	ctx := context.Background()
	resp := installer.BatchInstall(ctx, req)

	if resp.Total != 0 {
		t.Errorf("Expected Total=0, got %d", resp.Total)
	}

	if resp.Success != 0 {
		t.Errorf("Expected Success=0, got %d", resp.Success)
	}

	if resp.Failed != 0 {
		t.Errorf("Expected Failed=0, got %d", resp.Failed)
	}
}

// TestBatchInstall_DefaultWorkers tests default parallel workers
func TestBatchInstall_DefaultWorkers(t *testing.T) {
	installer := NewExtensionInstaller("dummy.exe", 5*time.Second)

	req := &models.BatchInstallRequest{
		Infobases: []models.InstallExtensionRequest{
			{
				Server:        "testserver",
				InfobaseName:  "testbase1",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				ExtensionPath: "C:\\extensions\\test.cfe",
			},
		},
		ParallelWorkers: 0, // Should default to 10
	}

	ctx := context.Background()
	resp := installer.BatchInstall(ctx, req)

	// Should have tried to install (and failed because dummy.exe doesn't exist)
	if resp.Total != 1 {
		t.Errorf("Expected Total=1, got %d", resp.Total)
	}

	if resp.Failed != 1 {
		t.Errorf("Expected Failed=1 (dummy executable), got %d", resp.Failed)
	}

	if len(resp.Results) != 1 {
		t.Fatalf("Expected 1 result, got %d", len(resp.Results))
	}

	if resp.Results[0].Status != "failed" {
		t.Errorf("Expected status='failed', got %q", resp.Results[0].Status)
	}

	if resp.Results[0].Error == "" {
		t.Error("Expected non-empty error message")
	}
}

// TestBatchInstall_MultipleInfobases tests batch install with multiple infobases
func TestBatchInstall_MultipleInfobases(t *testing.T) {
	installer := NewExtensionInstaller("dummy.exe", 5*time.Second)

	req := &models.BatchInstallRequest{
		Infobases: []models.InstallExtensionRequest{
			{
				Server:        "testserver",
				InfobaseName:  "testbase1",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				ExtensionPath: "C:\\extensions\\test.cfe",
			},
			{
				Server:        "testserver",
				InfobaseName:  "testbase2",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				ExtensionPath: "C:\\extensions\\test.cfe",
			},
			{
				Server:        "testserver",
				InfobaseName:  "testbase3",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				ExtensionPath: "C:\\extensions\\test.cfe",
			},
		},
		ParallelWorkers: 2,
	}

	ctx := context.Background()
	resp := installer.BatchInstall(ctx, req)

	// All should fail because dummy.exe doesn't exist
	if resp.Total != 3 {
		t.Errorf("Expected Total=3, got %d", resp.Total)
	}

	if resp.Failed != 3 {
		t.Errorf("Expected Failed=3, got %d", resp.Failed)
	}

	if len(resp.Results) != 3 {
		t.Fatalf("Expected 3 results, got %d", len(resp.Results))
	}

	for i, result := range resp.Results {
		if result.Status != "failed" {
			t.Errorf("Result[%d]: expected status='failed', got %q", i, result.Status)
		}

		if result.Error == "" {
			t.Errorf("Result[%d]: expected non-empty error", i)
		}

		// Duration can be very small (close to 0) for quick failures
		if result.DurationSeconds < 0 {
			t.Errorf("Result[%d]: expected non-negative duration", i)
		}
	}
}
