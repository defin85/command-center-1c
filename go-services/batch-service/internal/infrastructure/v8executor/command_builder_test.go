package v8executor

import (
	"strings"
	"testing"
)

// TestBuildInstallLoadCommand tests the LoadCfg command builder
func TestBuildInstallLoadCommand(t *testing.T) {
	args, err := BuildInstallLoadCommand(
		"testserver",
		"testbase",
		"admin",
		"pass",
		"TestExt",
		"C:\\extensions\\test.cfe",
	)

	if err != nil {
		t.Fatalf("Unexpected error: %v", err)
	}

	// Verify command structure
	expected := []string{
		"DESIGNER",
		"/F", "testserver\\testbase",
		"/N", "admin",
		"/P", "pass",
		"/LoadCfg", "C:\\extensions\\test.cfe",
		"-Extension", "TestExt",
	}

	if len(args) != len(expected) {
		t.Fatalf("Expected %d args, got %d", len(expected), len(args))
	}

	for i, arg := range expected {
		if args[i] != arg {
			t.Errorf("Arg[%d]: expected %q, got %q", i, arg, args[i])
		}
	}
}

// TestBuildInstallLoadCommand_Validation tests input validation
func TestBuildInstallLoadCommand_Validation(t *testing.T) {
	testCases := []struct {
		name          string
		server        string
		infobase      string
		username      string
		password      string
		extensionName string
		extensionPath string
		expectError   string
	}{
		{
			name:          "empty server",
			server:        "",
			infobase:      "testbase",
			username:      "admin",
			password:      "pass",
			extensionName: "TestExt",
			extensionPath: "C:\\test.cfe",
			expectError:   "server cannot be empty",
		},
		{
			name:          "empty infobase",
			server:        "testserver",
			infobase:      "",
			username:      "admin",
			password:      "pass",
			extensionName: "TestExt",
			extensionPath: "C:\\test.cfe",
			expectError:   "infobase cannot be empty",
		},
		{
			name:          "empty extension name",
			server:        "testserver",
			infobase:      "testbase",
			username:      "admin",
			password:      "pass",
			extensionName: "",
			extensionPath: "C:\\test.cfe",
			expectError:   "extension name cannot be empty",
		},
		{
			name:          "empty extension path",
			server:        "testserver",
			infobase:      "testbase",
			username:      "admin",
			password:      "pass",
			extensionName: "TestExt",
			extensionPath: "",
			expectError:   "extension path cannot be empty",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := BuildInstallLoadCommand(
				tc.server,
				tc.infobase,
				tc.username,
				tc.password,
				tc.extensionName,
				tc.extensionPath,
			)

			if err == nil {
				t.Fatal("Expected validation error, got nil")
			}

			if !strings.Contains(err.Error(), tc.expectError) {
				t.Errorf("Expected error containing %q, got: %v", tc.expectError, err)
			}
		})
	}
}

// TestBuildInstallUpdateCommand tests the UpdateDBCfg command builder
func TestBuildInstallUpdateCommand(t *testing.T) {
	args, err := BuildInstallUpdateCommand(
		"testserver",
		"testbase",
		"admin",
		"pass",
		"TestExt",
	)

	if err != nil {
		t.Fatalf("Unexpected error: %v", err)
	}

	// Verify command structure
	expected := []string{
		"DESIGNER",
		"/F", "testserver\\testbase",
		"/N", "admin",
		"/P", "pass",
		"/UpdateDBCfg",
		"-Extension", "TestExt",
	}

	if len(args) != len(expected) {
		t.Fatalf("Expected %d args, got %d", len(expected), len(args))
	}

	for i, arg := range expected {
		if args[i] != arg {
			t.Errorf("Arg[%d]: expected %q, got %q", i, arg, args[i])
		}
	}
}

// TestBuildUpdateCommand tests the UpdateDBCfg command builder
func TestBuildUpdateCommand(t *testing.T) {
	args, err := BuildUpdateCommand(
		"testserver",
		"testbase",
		"admin",
		"pass",
		"TestExt",
	)

	if err != nil {
		t.Fatalf("Unexpected error: %v", err)
	}

	// Verify command structure
	expected := []string{
		"DESIGNER",
		"/F", "testserver\\testbase",
		"/N", "admin",
		"/P", "pass",
		"/UpdateDBCfg",
		"-Extension", "TestExt",
	}

	if len(args) != len(expected) {
		t.Fatalf("Expected %d args, got %d", len(expected), len(args))
	}

	for i, arg := range expected {
		if args[i] != arg {
			t.Errorf("Arg[%d]: expected %q, got %q", i, arg, args[i])
		}
	}
}

// TestBuildDumpCommand tests the DumpCfg command builder
func TestBuildDumpCommand(t *testing.T) {
	args, err := BuildDumpCommand(
		"testserver",
		"testbase",
		"admin",
		"pass",
		"TestExt",
		"C:\\backup\\test.cfe",
	)

	if err != nil {
		t.Fatalf("Unexpected error: %v", err)
	}

	// Verify command structure
	expected := []string{
		"DESIGNER",
		"/F", "testserver\\testbase",
		"/N", "admin",
		"/P", "pass",
		"/DumpCfg", "C:\\backup\\test.cfe",
		"-Extension", "TestExt",
	}

	if len(args) != len(expected) {
		t.Fatalf("Expected %d args, got %d", len(expected), len(args))
	}

	for i, arg := range expected {
		if args[i] != arg {
			t.Errorf("Arg[%d]: expected %q, got %q", i, arg, args[i])
		}
	}
}

// TestBuildDumpCommand_Validation tests input validation
func TestBuildDumpCommand_Validation(t *testing.T) {
	testCases := []struct {
		name          string
		server        string
		infobase      string
		username      string
		password      string
		extensionName string
		outputPath    string
		expectError   string
	}{
		{
			name:          "empty server",
			server:        "",
			infobase:      "testbase",
			username:      "admin",
			password:      "pass",
			extensionName: "TestExt",
			outputPath:    "C:\\backup\\test.cfe",
			expectError:   "server cannot be empty",
		},
		{
			name:          "empty infobase",
			server:        "testserver",
			infobase:      "",
			username:      "admin",
			password:      "pass",
			extensionName: "TestExt",
			outputPath:    "C:\\backup\\test.cfe",
			expectError:   "infobase cannot be empty",
		},
		{
			name:          "empty extension name",
			server:        "testserver",
			infobase:      "testbase",
			username:      "admin",
			password:      "pass",
			extensionName: "",
			outputPath:    "C:\\backup\\test.cfe",
			expectError:   "extension name cannot be empty",
		},
		{
			name:          "empty output path",
			server:        "testserver",
			infobase:      "testbase",
			username:      "admin",
			password:      "pass",
			extensionName: "TestExt",
			outputPath:    "",
			expectError:   "output path cannot be empty",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := BuildDumpCommand(
				tc.server,
				tc.infobase,
				tc.username,
				tc.password,
				tc.extensionName,
				tc.outputPath,
			)

			if err == nil {
				t.Fatal("Expected validation error, got nil")
			}

			if !strings.Contains(err.Error(), tc.expectError) {
				t.Errorf("Expected error containing %q, got: %v", tc.expectError, err)
			}
		})
	}
}

// TestBuildRollbackCommand tests the RollbackCfg command builder
func TestBuildRollbackCommand(t *testing.T) {
	args, err := BuildRollbackCommand(
		"testserver",
		"testbase",
		"admin",
		"pass",
		"TestExt",
	)

	if err != nil {
		t.Fatalf("Unexpected error: %v", err)
	}

	// Verify command structure
	expected := []string{
		"DESIGNER",
		"/F", "testserver\\testbase",
		"/N", "admin",
		"/P", "pass",
		"/RollbackCfg",
		"-Extension", "TestExt",
	}

	if len(args) != len(expected) {
		t.Fatalf("Expected %d args, got %d", len(expected), len(args))
	}

	for i, arg := range expected {
		if args[i] != arg {
			t.Errorf("Arg[%d]: expected %q, got %q", i, arg, args[i])
		}
	}
}

// TestBuildRollbackCommand_Validation tests input validation
func TestBuildRollbackCommand_Validation(t *testing.T) {
	testCases := []struct {
		name          string
		server        string
		infobase      string
		username      string
		password      string
		extensionName string
		expectError   string
	}{
		{
			name:          "empty server",
			server:        "",
			infobase:      "testbase",
			username:      "admin",
			password:      "pass",
			extensionName: "TestExt",
			expectError:   "server cannot be empty",
		},
		{
			name:          "empty infobase",
			server:        "testserver",
			infobase:      "",
			username:      "admin",
			password:      "pass",
			extensionName: "TestExt",
			expectError:   "infobase cannot be empty",
		},
		{
			name:          "empty extension name",
			server:        "testserver",
			infobase:      "testbase",
			username:      "admin",
			password:      "pass",
			extensionName: "",
			expectError:   "extension name cannot be empty",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := BuildRollbackCommand(
				tc.server,
				tc.infobase,
				tc.username,
				tc.password,
				tc.extensionName,
			)

			if err == nil {
				t.Fatal("Expected validation error, got nil")
			}

			if !strings.Contains(err.Error(), tc.expectError) {
				t.Errorf("Expected error containing %q, got: %v", tc.expectError, err)
			}
		})
	}
}
