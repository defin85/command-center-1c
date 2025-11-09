package metadata

import (
	"crypto/md5"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/command-center-1c/batch-service/internal/infrastructure/v8executor"
	"github.com/command-center-1c/batch-service/internal/models"
	"github.com/google/uuid"
	"go.uber.org/zap"
)

// Extractor handles metadata extraction from .cfe extension files
type Extractor struct {
	v8executor *v8executor.V8Executor
	parser     *Parser
	logger     *zap.Logger
}

// NewExtractor creates new Extractor instance
func NewExtractor(v8exec *v8executor.V8Executor, parser *Parser, logger *zap.Logger) *Extractor {
	return &Extractor{
		v8executor: v8exec,
		parser:     parser,
		logger:     logger,
	}
}

// ExtractFromCFE extracts complete metadata from .cfe extension file
// Flow:
// 1. Create temporary database
// 2. Load extension into database
// 3. Dump extension to XML files
// 4. Parse XML files
// 5. Count objects
// 6. Cleanup (delete extension, temp files, temp database)
// 7. Return ExtensionMetadata
func (e *Extractor) ExtractFromCFE(cfePath string) (*models.ExtensionMetadata, error) {
	e.logger.Info("extracting metadata from .cfe file", zap.String("path", cfePath))

	// Validate .cfe file exists
	if _, err := os.Stat(cfePath); os.IsNotExist(err) {
		return nil, fmt.Errorf("cfe file not found: %s", cfePath)
	}

	// Get file metadata (size, modification date, checksum)
	fileInfo, err := os.Stat(cfePath)
	if err != nil {
		return nil, fmt.Errorf("failed to stat cfe file: %w", err)
	}

	// Calculate MD5 checksum
	checksum, err := e.calculateMD5(cfePath)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate MD5 checksum: %w", err)
	}

	// Generate unique extension name for temporary use
	tempExtName := fmt.Sprintf("TempExtract_%s", uuid.New().String()[:8])

	// Step 1: Create temporary database
	tempDBPath, err := e.createTempDatabase()
	if err != nil {
		return nil, fmt.Errorf("failed to create temporary database: %w", err)
	}
	// Ensure cleanup on exit
	defer func() {
		if cleanupErr := e.cleanupTempDatabase(tempDBPath); cleanupErr != nil {
			e.logger.Warn("failed to cleanup temp database", zap.Error(cleanupErr))
		}
	}()

	// Step 2: Load extension into database
	if err := e.v8executor.LoadExtension(tempDBPath, cfePath, tempExtName); err != nil {
		return nil, fmt.Errorf("failed to load extension into database: %w", err)
	}

	// Step 3: Dump extension to XML
	tempXMLDir, err := e.createTempXMLDir()
	if err != nil {
		return nil, fmt.Errorf("failed to create temp XML directory: %w", err)
	}
	defer func() {
		if cleanupErr := e.cleanupTempFiles(tempXMLDir); cleanupErr != nil {
			e.logger.Warn("failed to cleanup temp XML files", zap.Error(cleanupErr))
		}
	}()

	if err := e.v8executor.DumpExtensionToXML(tempDBPath, tempXMLDir, tempExtName); err != nil {
		return nil, fmt.Errorf("failed to dump extension to XML: %w", err)
	}

	// Step 4: Parse Configuration.xml
	configXMLPath := filepath.Join(tempXMLDir, "Configuration.xml")
	config, err := e.parser.ParseConfigurationXML(configXMLPath)
	if err != nil {
		return nil, fmt.Errorf("failed to parse Configuration.xml: %w", err)
	}

	// Step 5: Count objects
	objectsCount, err := e.parser.CountObjects(tempXMLDir)
	if err != nil {
		return nil, fmt.Errorf("failed to count objects: %w", err)
	}

	// Step 6: Extract additional metadata
	author := e.parser.ExtractAuthor(config)
	description := e.parser.ExtractDescription(config)
	minVersion, maxVersion := e.parser.ExtractPlatformVersions(config)

	// Step 7: Delete extension from database (cleanup)
	if err := e.v8executor.DeleteExtension(tempDBPath, tempExtName); err != nil {
		e.logger.Warn("failed to delete extension from database (non-critical)", zap.Error(err))
		// Non-critical - continue
	}

	// Build final metadata structure
	metadata := &models.ExtensionMetadata{
		Name:               config.Name,
		Version:            config.Version,
		Author:             author,
		Description:        description,
		PlatformVersionMin: minVersion,
		PlatformVersionMax: maxVersion,
		Dependencies:       []string{}, // TODO: Extract dependencies if available in XML
		SizeBytes:          fileInfo.Size(),
		ModificationDate:   fileInfo.ModTime(),
		ChecksumMD5:        checksum,
		ObjectsCount:       objectsCount,
	}

	e.logger.Info("metadata extraction completed successfully",
		zap.String("name", metadata.Name),
		zap.String("version", metadata.Version),
		zap.Int64("size_bytes", metadata.SizeBytes),
		zap.Int("total_objects", e.countTotalObjects(objectsCount)))

	return metadata, nil
}

// createTempDatabase creates temporary file-based 1C infobase
func (e *Extractor) createTempDatabase() (string, error) {
	// Use system temp directory
	tmpDir := os.TempDir()

	// Generate unique database name
	dbName := fmt.Sprintf("metadata_db_%s", uuid.New().String())
	dbPath := filepath.Join(tmpDir, dbName)

	e.logger.Debug("creating temporary database", zap.String("path", dbPath))

	// Create infobase using V8Executor
	if err := e.v8executor.CreateInfobase(dbPath); err != nil {
		return "", fmt.Errorf("failed to create infobase: %w", err)
	}

	return dbPath, nil
}

// createTempXMLDir creates temporary directory for XML dump
func (e *Extractor) createTempXMLDir() (string, error) {
	tmpDir := os.TempDir()
	xmlDirName := fmt.Sprintf("ext_xml_%s", uuid.New().String())
	xmlDirPath := filepath.Join(tmpDir, xmlDirName)

	if err := os.MkdirAll(xmlDirPath, 0755); err != nil {
		return "", fmt.Errorf("failed to create XML directory: %w", err)
	}

	e.logger.Debug("created temporary XML directory", zap.String("path", xmlDirPath))

	return xmlDirPath, nil
}

// cleanupTempDatabase removes temporary database directory and all its contents
func (e *Extractor) cleanupTempDatabase(dbPath string) error {
	e.logger.Debug("cleaning up temporary database", zap.String("path", dbPath))

	if err := os.RemoveAll(dbPath); err != nil {
		return fmt.Errorf("failed to remove temp database: %w", err)
	}

	return nil
}

// cleanupTempFiles removes temporary XML files directory
func (e *Extractor) cleanupTempFiles(xmlDir string) error {
	e.logger.Debug("cleaning up temporary XML files", zap.String("path", xmlDir))

	if err := os.RemoveAll(xmlDir); err != nil {
		return fmt.Errorf("failed to remove temp XML directory: %w", err)
	}

	return nil
}

// calculateMD5 calculates MD5 checksum of file
func (e *Extractor) calculateMD5(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("failed to open file: %w", err)
	}
	defer file.Close()

	hash := md5.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", fmt.Errorf("failed to calculate hash: %w", err)
	}

	return fmt.Sprintf("%x", hash.Sum(nil)), nil
}

// countTotalObjects counts total number of objects across all types
func (e *Extractor) countTotalObjects(objectsCount map[string]int) int {
	total := 0
	for _, count := range objectsCount {
		total += count
	}
	return total
}
