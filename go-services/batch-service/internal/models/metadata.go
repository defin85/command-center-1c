package models

import (
	"encoding/xml"
	"time"
)

// ExtensionMetadata represents complete metadata extracted from .cfe extension file
type ExtensionMetadata struct {
	Name               string         `json:"name"`
	Version            string         `json:"version"`
	Author             string         `json:"author,omitempty"`
	Description        string         `json:"description,omitempty"`
	PlatformVersionMin string         `json:"platform_version_min,omitempty"`
	PlatformVersionMax string         `json:"platform_version_max,omitempty"`
	Dependencies       []string       `json:"dependencies,omitempty"`
	SizeBytes          int64          `json:"size_bytes"`
	ModificationDate   time.Time      `json:"modification_date"`
	ChecksumMD5        string         `json:"checksum_md5"`
	ObjectsCount       map[string]int `json:"objects_count"`
}

// ConfigurationXML represents the structure of Configuration.xml after DumpConfigToFiles
// This is the main metadata file that contains extension properties
type ConfigurationXML struct {
	XMLName xml.Name `xml:"MetaDataObject"`
	Name    string   `xml:"Configuration>Properties>Name"`
	Version string   `xml:"Configuration>Properties>Version"`
	Vendor  string   `xml:"Configuration>Properties>Vendor"` // Author
	Comment string   `xml:"Configuration>Properties>Comment"` // Description

	// Additional properties that may be useful
	Synonym    SynonymNode         `xml:"Configuration>Properties>Synonym"`
	ConfigInfo ConfigurationInfo   `xml:"Configuration>Properties"`
}

// SynonymNode represents multi-language synonym
type SynonymNode struct {
	Items []SynonymItem `xml:"item"`
}

// SynonymItem represents single language synonym
type SynonymItem struct {
	Lang    string `xml:"lang"`
	Content string `xml:"content"`
}

// ConfigurationInfo contains additional configuration metadata
type ConfigurationInfo struct {
	CompatibilityMode            string `xml:"CompatibilityMode,omitempty"`
	ConfigurationExtensionPurpose string `xml:"ConfigurationExtensionPurpose,omitempty"`
}

// ObjectTypes represents 1C configuration object types that can be counted
var ObjectTypes = []string{
	"Catalogs",
	"Documents",
	"Reports",
	"DataProcessors",
	"ChartsOfAccounts",
	"ChartsOfCalculationTypes",
	"ChartsOfCharacteristicTypes",
	"InformationRegisters",
	"AccumulationRegisters",
	"AccountingRegisters",
	"CalculationRegisters",
	"BusinessProcesses",
	"Tasks",
	"ExchangePlans",
	"Constants",
	"Enums",
	"Roles",
	"CommonModules",
	"SessionParameters",
	"FunctionalOptions",
	"DefinedTypes",
	"WebServices",
	"HTTPServices",
	"WSReferences",
	"Subsystems",
}

// GetObjectTypesMap returns initialized map with all object types set to 0
func GetObjectTypesMap() map[string]int {
	counts := make(map[string]int)
	for _, objType := range ObjectTypes {
		counts[objType] = 0
	}
	return counts
}
