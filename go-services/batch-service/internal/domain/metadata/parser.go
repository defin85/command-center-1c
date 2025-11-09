package metadata

import (
	"encoding/xml"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/command-center-1c/batch-service/internal/models"
	"go.uber.org/zap"
)

// Parser handles XML parsing of dumped configuration files
type Parser struct {
	logger *zap.Logger
}

// NewParser creates new Parser instance
func NewParser(logger *zap.Logger) *Parser {
	return &Parser{
		logger: logger,
	}
}

// ParseConfigurationXML reads and parses Configuration.xml
// This file contains main metadata: name, version, author, description
func (p *Parser) ParseConfigurationXML(xmlPath string) (*models.ConfigurationXML, error) {
	p.logger.Debug("parsing Configuration.xml", zap.String("path", xmlPath))

	// Read file
	data, err := os.ReadFile(xmlPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read Configuration.xml: %w", err)
	}

	// Parse XML
	var config models.ConfigurationXML
	if err := xml.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse Configuration.xml: %w", err)
	}

	p.logger.Debug("Configuration.xml parsed successfully",
		zap.String("name", config.Name),
		zap.String("version", config.Version),
		zap.String("vendor", config.Vendor))

	return &config, nil
}

// CountObjects counts configuration objects by type
// Walks through subdirectories and counts .xml files
// Returns map: {"catalogs": 5, "documents": 3, ...}
func (p *Parser) CountObjects(xmlDir string) (map[string]int, error) {
	p.logger.Debug("counting objects", zap.String("xmlDir", xmlDir))

	counts := models.GetObjectTypesMap()

	// Walk through each object type directory
	for _, objType := range models.ObjectTypes {
		dirPath := filepath.Join(xmlDir, objType)

		// Check if directory exists
		info, err := os.Stat(dirPath)
		if os.IsNotExist(err) {
			// Directory doesn't exist - no objects of this type
			counts[objType] = 0
			continue
		}
		if err != nil {
			return nil, fmt.Errorf("failed to stat directory %s: %w", dirPath, err)
		}
		if !info.IsDir() {
			// Not a directory - skip
			continue
		}

		// Count .xml files in directory
		count, err := p.countXMLFiles(dirPath)
		if err != nil {
			return nil, fmt.Errorf("failed to count XML files in %s: %w", dirPath, err)
		}

		counts[objType] = count
	}

	// Log summary
	totalObjects := 0
	for _, count := range counts {
		totalObjects += count
	}
	p.logger.Debug("objects counted",
		zap.Int("total", totalObjects),
		zap.Any("breakdown", counts))

	return counts, nil
}

// countXMLFiles counts .xml files in a directory (non-recursive)
func (p *Parser) countXMLFiles(dirPath string) (int, error) {
	entries, err := os.ReadDir(dirPath)
	if err != nil {
		return 0, fmt.Errorf("failed to read directory: %w", err)
	}

	count := 0
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		// Count only .xml files (case-insensitive)
		if strings.HasSuffix(strings.ToLower(entry.Name()), ".xml") {
			count++
		}
	}

	return count, nil
}

// ExtractAuthor extracts author/vendor from Configuration.xml
// Returns Vendor field if present, otherwise empty string
func (p *Parser) ExtractAuthor(config *models.ConfigurationXML) string {
	if config.Vendor != "" {
		return config.Vendor
	}
	return ""
}

// ExtractDescription extracts description from Configuration.xml
// Priority: Comment field > Synonym > empty string
func (p *Parser) ExtractDescription(config *models.ConfigurationXML) string {
	if config.Comment != "" {
		return config.Comment
	}

	// Try to extract from Synonym (multi-language)
	if len(config.Synonym.Items) > 0 {
		// Prefer Russian, fallback to first available
		for _, item := range config.Synonym.Items {
			if item.Lang == "ru" {
				return item.Content
			}
		}
		// Return first available
		return config.Synonym.Items[0].Content
	}

	return ""
}

// ExtractPlatformVersions extracts platform version constraints
// Returns min and max platform versions if available
func (p *Parser) ExtractPlatformVersions(config *models.ConfigurationXML) (string, string) {
	// In Configuration.xml, platform versions might be in:
	// - CompatibilityMode field
	// - Separate MinPlatformVersion/MaxPlatformVersion fields (if they exist)

	// For now, we extract from CompatibilityMode if available
	// Format example: "Version8_3_20" or "DontUse"
	compatMode := config.ConfigInfo.CompatibilityMode
	if compatMode != "" && compatMode != "DontUse" {
		// Parse version from CompatibilityMode
		// Example: "Version8_3_20" -> "8.3.20.0"
		minVersion := parseCompatibilityMode(compatMode)
		// Max version is unknown - leave empty or set to very high value
		return minVersion, ""
	}

	// If no info available
	return "", ""
}

// parseCompatibilityMode converts 1C CompatibilityMode to version string
// Example: "Version8_3_20" -> "8.3.20.0"
func parseCompatibilityMode(compatMode string) string {
	// Remove "Version" prefix
	version := strings.TrimPrefix(compatMode, "Version")

	// Replace underscores with dots
	version = strings.ReplaceAll(version, "_", ".")

	// Add .0 suffix if needed
	if !strings.HasSuffix(version, ".0") {
		version += ".0"
	}

	return version
}
