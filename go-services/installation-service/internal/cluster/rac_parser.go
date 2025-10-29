package cluster

import (
	"fmt"
	"strconv"
	"strings"

	"golang.org/x/text/encoding/charmap"
)

// decodeWindows1251 decodes Windows-1251 encoded bytes to UTF-8 string
func decodeWindows1251(data []byte) (string, error) {
	decoder := charmap.Windows1251.NewDecoder()
	decoded, err := decoder.Bytes(data)
	if err != nil {
		return "", fmt.Errorf("failed to decode Windows-1251: %w", err)
	}
	return string(decoded), nil
}

// parseKeyValue parses a line in format "key : value" and returns key and value
func parseKeyValue(line string) (string, string) {
	parts := strings.SplitN(line, ":", 2)
	if len(parts) != 2 {
		return "", ""
	}
	key := strings.TrimSpace(parts[0])
	value := strings.TrimSpace(parts[1])
	return key, value
}

// parseClusterInfo parses the output of "rac cluster list" command
func parseClusterInfo(output []byte) (*ClusterInfo, error) {
	decoded, err := decodeWindows1251(output)
	if err != nil {
		return nil, fmt.Errorf("failed to decode cluster info: %w", err)
	}

	cluster := &ClusterInfo{}
	lines := strings.Split(decoded, "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		key, value := parseKeyValue(line)
		switch key {
		case "cluster":
			cluster.UUID = value
		case "name":
			cluster.Name = value
		case "host":
			cluster.Host = value
		case "port":
			if port, err := strconv.Atoi(value); err == nil {
				cluster.Port = port
			}
		}
	}

	if cluster.UUID == "" {
		return nil, fmt.Errorf("cluster UUID not found in output")
	}

	return cluster, nil
}

// parseInfobaseSummaryList parses the output of "rac infobase summary list" command
func parseInfobaseSummaryList(output []byte) ([]InfobaseInfo, error) {
	decoded, err := decodeWindows1251(output)
	if err != nil {
		return nil, fmt.Errorf("failed to decode infobase summary: %w", err)
	}

	var infobases []InfobaseInfo
	var current InfobaseInfo
	lines := strings.Split(decoded, "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)

		// Empty line indicates end of current record
		if line == "" {
			if current.UUID != "" {
				infobases = append(infobases, current)
				current = InfobaseInfo{}
			}
			continue
		}

		key, value := parseKeyValue(line)
		switch key {
		case "infobase":
			// New infobase record, save previous if exists
			if current.UUID != "" {
				infobases = append(infobases, current)
			}
			current = InfobaseInfo{UUID: value}
		case "name":
			current.Name = value
		case "descr":
			current.Description = value
		}
	}

	// Add the last record if exists
	if current.UUID != "" {
		infobases = append(infobases, current)
	}

	return infobases, nil
}

// parseInfobaseDetails parses the output of "rac infobase info" command
func parseInfobaseDetails(output []byte) (InfobaseInfo, error) {
	decoded, err := decodeWindows1251(output)
	if err != nil {
		return InfobaseInfo{}, fmt.Errorf("failed to decode infobase details: %w", err)
	}

	infobase := InfobaseInfo{}
	lines := strings.Split(decoded, "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		key, value := parseKeyValue(line)
		switch key {
		case "infobase":
			infobase.UUID = value
		case "name":
			infobase.Name = value
		case "descr":
			infobase.Description = value
		case "dbms":
			infobase.DBMS = value
		case "db-server":
			infobase.DBServer = value
		case "db-name":
			infobase.DBName = value
		case "db-user":
			infobase.DBUser = value
		case "security-level":
			if level, err := strconv.Atoi(value); err == nil {
				infobase.SecurityLevel = level
			}
		case "locale":
			infobase.Locale = value
		}
	}

	if infobase.UUID == "" {
		return InfobaseInfo{}, fmt.Errorf("infobase UUID not found in output")
	}

	// Generate connection string
	if infobase.DBServer != "" && infobase.Name != "" {
		infobase.ConnectionString = fmt.Sprintf("/S\"%s\\%s\"", infobase.DBServer, infobase.Name)
	}

	return infobase, nil
}

// mergeInfobaseDetails merges detailed information into summary info
func mergeInfobaseDetails(summary InfobaseInfo, details InfobaseInfo) InfobaseInfo {
	// Start with summary (has UUID, Name, Description)
	result := summary

	// Add details if present
	if details.DBMS != "" {
		result.DBMS = details.DBMS
	}
	if details.DBServer != "" {
		result.DBServer = details.DBServer
	}
	if details.DBName != "" {
		result.DBName = details.DBName
	}
	if details.DBUser != "" {
		result.DBUser = details.DBUser
	}
	if details.SecurityLevel != 0 {
		result.SecurityLevel = details.SecurityLevel
	}
	if details.Locale != "" {
		result.Locale = details.Locale
	}
	if details.ConnectionString != "" {
		result.ConnectionString = details.ConnectionString
	}

	return result
}
