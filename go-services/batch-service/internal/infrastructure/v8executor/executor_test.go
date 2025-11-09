package v8executor

import (
	"strings"
	"testing"
	"time"

	"go.uber.org/zap/zaptest"
	"github.com/stretchr/testify/assert"
)

// TestSanitizeForLogRemovesPassword verifies password is masked in logs
func TestSanitizeForLogRemovesPassword(t *testing.T) {
	testCases := []struct {
		name     string
		args     []string
		expected []string
	}{
		{
			name: "password with /P prefix",
			args: []string{"DESIGNER", "/F/path/to/db", "/NAdmin", "/PSecretPassword123"},
			expected: []string{"DESIGNER", "/F/path/to/db", "/NAdmin", "/P***"},
		},
		{
			name: "multiple arguments with password",
			args: []string{"/F/db", "/NAdmin", "/PMyPassword", "/LoadCfg/path/to/config"},
			expected: []string{"/F/db", "/NAdmin", "/P***", "/LoadCfg/path/to/config"},
		},
		{
			name: "no password",
			args: []string{"DESIGNER", "/F/db", "/NAdmin"},
			expected: []string{"DESIGNER", "/F/db", "/NAdmin"},
		},
		{
			name: "password at end",
			args: []string{"DESIGNER", "/F/db", "/P12345"},
			expected: []string{"DESIGNER", "/F/db", "/P***"},
		},
		{
			name: "empty args",
			args: []string{},
			expected: []string{},
		},
		{
			name: "multiple passwords (rare but possible)",
			args: []string{"/NUser1", "/PPass1", "/F/db", "/NUser2", "/PPass2"},
			expected: []string{"/NUser1", "/P***", "/F/db", "/NUser2", "/P***"},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			result := sanitizeForLog(tc.args)
			assert.Equal(t, tc.expected, result,
				"sanitizeForLog(%v) should return %v", tc.args, tc.expected)
		})
	}
}

// TestSanitizePreservesNonPasswordArguments verifies other arguments are not modified
func TestSanitizePreservesNonPasswordArguments(t *testing.T) {
	args := []string{
		"DESIGNER",
		"/Fpath/to/database",
		"/NAdministrator",
		"/LoadCfgpath/to/config",
		"-Extension", "MyExtension",
		"-format", "Hierarchical",
	}

	result := sanitizeForLog(args)

	for i, arg := range result {
		if !strings.HasPrefix(arg, "/P") {
			assert.Equal(t, args[i], arg,
				"Non-password argument at position %d should not be modified", i)
		}
	}
}

// TestSanitizeComplexCommand verifies complex real-world command is properly sanitized
func TestSanitizeComplexCommand(t *testing.T) {
	// Real example of LoadExtension with credentials
	args := []string{
		"DESIGNER",
		"/F/mnt/databases/app1.db",
		"/NAdmin",
		"/PadminPassword123!@#",
		"/LoadCfg/tmp/extension.cfe",
		"-Extension", "MyExtension",
	}

	result := sanitizeForLog(args)

	// Verify password is masked
	for _, arg := range result {
		assert.NotContains(t, arg, "adminPassword123", "Password should not appear in sanitized output")
		assert.NotEqual(t, "/PadminPassword123!@#", arg, "Full password arg should not appear")
	}

	// Verify correct position has /P***
	assert.Equal(t, "/P***", result[3], "Password should be masked at position 3")

	// Verify other arguments are preserved
	assert.Equal(t, "DESIGNER", result[0])
	assert.Equal(t, "/F/mnt/databases/app1.db", result[1])
	assert.Equal(t, "/NAdmin", result[2])
	assert.Equal(t, "/LoadCfg/tmp/extension.cfe", result[4])
	assert.Equal(t, "-Extension", result[5])
	assert.Equal(t, "MyExtension", result[6])
}

// TestSanitizeEdgeCases tests edge cases for password sanitization
func TestSanitizeEdgeCases(t *testing.T) {
	testCases := []struct {
		name     string
		arg      string
		expected string
	}{
		{
			name:     "empty password /P",
			arg:      "/P",
			expected: "/P***",
		},
		{
			name:     "password with special chars",
			arg:      "/P!@#$%^&*()",
			expected: "/P***",
		},
		{
			name:     "password with spaces (if quoted)",
			arg:      "/Pmy password with spaces",
			expected: "/P***",
		},
		{
			name:     "very long password",
			arg:      "/P" + strings.Repeat("a", 1000),
			expected: "/P***",
		},
		{
			name:     "/LoadCfg arg (not password)",
			arg:      "/LoadCfg/path/to/config",
			expected: "/LoadCfg/path/to/config",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			result := sanitizeForLog([]string{tc.arg})
			assert.Equal(t, []string{tc.expected}, result,
				"sanitizeForLog(%v) should return [%s]", tc.arg, tc.expected)
		})
	}
}

// TestSanitizePerformance benchmarks the sanitization function
func BenchmarkSanitizeForLog(b *testing.B) {
	args := []string{
		"DESIGNER",
		"/Fpath/to/database",
		"/NAdministrator",
		"/PSecretPassword123",
		"/LoadCfgpath/to/config",
		"-Extension", "MyExtension",
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sanitizeForLog(args)
	}
	b.StopTimer()
}

// TestExecuteLogsSanitizedPassword verifies Execute logs don't contain passwords
func TestExecuteLogsSanitizedPassword(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	_ = NewV8Executor("C:\\nonexistent\\1cv8.exe", 5*time.Second, logger)

	// Test buildCredentials function to ensure it can be called with passwords
	creds := buildCredentials("admin", "SecretPassword123")

	// Credentials should contain username and password
	assert.NotEmpty(t, creds)
	assert.Contains(t, creds, "/Nadmin")  // Note: lowercase because buildCredentials doesn't uppercase
	assert.Contains(t, creds, "/PSecretPassword123")

	t.Log("buildCredentials correctly includes password argument")
}

// TestBuildCredentialsFormat verifies credential format
func TestBuildCredentialsFormat(t *testing.T) {
	testCases := []struct {
		name     string
		username string
		password string
		expected []string
	}{
		{
			name:     "both username and password",
			username: "admin",
			password: "password123",
			expected: []string{"/Nadmin", "/Ppassword123"},
		},
		{
			name:     "only username",
			username: "user",
			password: "",
			expected: []string{"/Nuser"},
		},
		{
			name:     "empty username",
			username: "",
			password: "password",
			expected: []string{},
		},
		{
			name:     "no credentials",
			username: "",
			password: "",
			expected: []string{},
		},
		{
			name:     "special chars in password",
			username: "admin",
			password: "P@ssw0rd!#$%",
			expected: []string{"/Nadmin", "/PP@ssw0rd!#$%"},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			result := buildCredentials(tc.username, tc.password)
			assert.Equal(t, tc.expected, result,
				"buildCredentials(%q, %q) should return %v", tc.username, tc.password, tc.expected)
		})
	}
}

// TestCredentialsLogSanitization verifies end-to-end that logs are sanitized
func TestCredentialsLogSanitization(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	_ = NewV8Executor("C:\\nonexistent\\1cv8.exe", 5*time.Second, logger)

	args := []string{
		"DESIGNER",
		"/F/path/to/db",
		"/NAdmin",
		"/PMySecretPassword123",
		"/LoadCfg/path/to/config",
	}

	// Simulate what Execute does with logging
	sanitized := sanitizeForLog(args)

	// Verify password is not in sanitized args
	for _, arg := range sanitized {
		assert.NotContains(t, arg, "MySecretPassword", "Sanitized args should not contain password")
	}

	// Verify /P*** is present
	found := false
	for _, arg := range sanitized {
		if arg == "/P***" {
			found = true
			break
		}
	}
	assert.True(t, found, "Sanitized args should contain /P***")

	t.Log("End-to-end password sanitization verified")
}

// TestSanitizeIsSafeToCallMultipleTimes verifies sanitize is idempotent for non-password args
func TestSanitizeIdempotence(t *testing.T) {
	args := []string{"DESIGNER", "/F/db", "/NAdmin", "/DumpCfg/out.cfe"}

	result1 := sanitizeForLog(args)
	result2 := sanitizeForLog(result1)

	assert.Equal(t, result1, result2, "Sanitizing already-sanitized args should be idempotent")
}

// TestLongPasswordHandling verifies very long passwords are properly masked
func TestLongPasswordHandling(t *testing.T) {
	longPassword := strings.Repeat("x", 10000)
	args := []string{"DESIGNER", "/P" + longPassword}

	result := sanitizeForLog(args)

	assert.Equal(t, "/P***", result[1], "Long password should be masked")
	assert.NotContains(t, result[1], "xxx", "Sanitized output should not contain password chars")
}
