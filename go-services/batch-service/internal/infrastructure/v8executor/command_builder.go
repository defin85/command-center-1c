package v8executor

import (
	"fmt"
	"strings"
)

// BuildDeleteCommand builds command arguments for deleting a 1C extension
// Format: 1cv8.exe DESIGNER /DisableStartupMessages /DisableStartupDialogs /S"server\infobase" /N"user" /P"pass" /DeleteCfg -Extension name
func BuildDeleteCommand(server, infobase, username, password, extensionName string) []string {
	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/DeleteCfg",
		"-Extension", extensionName,
	}
}

// BuildListCommand builds command arguments for listing 1C extensions
// Format: 1cv8.exe DESIGNER /DisableStartupMessages /DisableStartupDialogs /S"server\infobase" /N"user" /P"pass" /ConfigurationRepositoryReport reportPath
func BuildListCommand(server, infobase, username, password, reportPath string) []string {
	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/ConfigurationRepositoryReport", reportPath,
	}
}

// BuildInstallLoadCommand builds command arguments for loading extension (step 1 of install)
// Format: 1cv8.exe DESIGNER /DisableStartupMessages /DisableStartupDialogs /S"server\infobase" /N"user" /P"pass" /LoadCfg extensionPath -Extension name
func BuildInstallLoadCommand(server, infobase, username, password, extensionName, extensionPath string) ([]string, error) {
	// Validate inputs
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(extensionName) == "" {
		return nil, fmt.Errorf("extension name cannot be empty")
	}
	if strings.TrimSpace(extensionPath) == "" {
		return nil, fmt.Errorf("extension path cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/LoadCfg", extensionPath,
		"-Extension", extensionName,
	}, nil
}

// BuildInstallUpdateCommand builds command arguments for updating DB config (step 2 of install)
// Format: 1cv8.exe DESIGNER /DisableStartupMessages /DisableStartupDialogs /S"server\infobase" /N"user" /P"pass" /UpdateDBCfg -Extension name
func BuildInstallUpdateCommand(server, infobase, username, password, extensionName string) ([]string, error) {
	// Validate inputs
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(extensionName) == "" {
		return nil, fmt.Errorf("extension name cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/UpdateDBCfg",
		"-Extension", extensionName,
	}, nil
}

// BuildUpdateCommand builds command arguments for updating extension DB config
// Format: 1cv8.exe DESIGNER /DisableStartupMessages /DisableStartupDialogs /S"server\infobase" /N"user" /P"pass" /UpdateDBCfg -Extension name
func BuildUpdateCommand(server, infobase, username, password, extensionName string) ([]string, error) {
	// Validate inputs
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(extensionName) == "" {
		return nil, fmt.Errorf("extension name cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/UpdateDBCfg",
		"-Extension", extensionName,
	}, nil
}

// BuildDumpCommand builds command arguments for dumping extension to file
// Format: 1cv8.exe DESIGNER /DisableStartupMessages /DisableStartupDialogs /S"server\infobase" /N"user" /P"pass" /DumpCfg outputPath -Extension name
func BuildDumpCommand(server, infobase, username, password, extensionName, outputPath string) ([]string, error) {
	// Validate inputs
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(extensionName) == "" {
		return nil, fmt.Errorf("extension name cannot be empty")
	}
	if strings.TrimSpace(outputPath) == "" {
		return nil, fmt.Errorf("output path cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/DumpCfg", outputPath,
		"-Extension", extensionName,
	}, nil
}

// BuildRollbackCommand builds command arguments for rolling back extension
// Format: 1cv8.exe DESIGNER /DisableStartupMessages /DisableStartupDialogs /S"server\infobase" /N"user" /P"pass" /RollbackCfg -Extension name
func BuildRollbackCommand(server, infobase, username, password, extensionName string) ([]string, error) {
	// Validate inputs
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(extensionName) == "" {
		return nil, fmt.Errorf("extension name cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/RollbackCfg",
		"-Extension", extensionName,
	}, nil
}
