package poolops

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"gopkg.in/yaml.v3"
)

const (
	defaultPublicationCompatibilityProfilePath     = "openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.yaml"
	defaultPublicationCompatibilityConfigurationID = "1c-accounting-3.0-standard-odata"
	defaultPublicationWriteContentType             = "application/json;odata=nometadata"
)

type publicationCompatibilityInput struct {
	ProfilePath           string
	ConfigurationID       string
	CompatibilityMode     string
	WriteContentType      string
	ReleaseProfileVersion string
}

type publicationCompatibilityReport struct {
	ProfilePath           string
	ProfileVersion        string
	ConfigurationID       string
	WriteContentType      string
	ReleaseProfileVersion string
}

type odataCompatibilityProfile struct {
	ProfileVersion string                        `yaml:"profile_version"`
	Entries        []odataCompatibilityEntry     `yaml:"entries"`
	RolloutGate    odataCompatibilityRolloutGate `yaml:"rollout_gate"`
}

type odataCompatibilityEntry struct {
	ConfigurationID    string                      `yaml:"configuration_id"`
	VerificationStatus string                      `yaml:"verification_status"`
	MediaTypePolicy    odataCompatibilityMediaType `yaml:"media_type_policy"`
}

type odataCompatibilityMediaType struct {
	DefaultWriteContentType string                         `yaml:"default_write_content_type"`
	Accepts                 []string                       `yaml:"accepts"`
	Rejects                 []string                       `yaml:"rejects"`
	LegacyModeLE837         odataCompatibilityLegacyPolicy `yaml:"legacy_mode_le_8_3_7"`
}

type odataCompatibilityLegacyPolicy struct {
	Supported          bool   `yaml:"supported"`
	RequiredPolicyNote string `yaml:"required_policy_note"`
}

type odataCompatibilityRolloutGate struct {
	RequireApprovedEntry               *bool `yaml:"require_approved_entry"`
	RequireProfileVersionInRelease     *bool `yaml:"require_profile_version_in_release"`
	BlockOnIncompatibleMediaTypePolicy *bool `yaml:"block_on_incompatible_media_type_policy"`
}

func resolvePublicationCompatibilityInput(
	publicationPayload map[string]interface{},
	cfg PublicationTransportConfig,
) publicationCompatibilityInput {
	input := publicationCompatibilityInput{
		ProfilePath:           strings.TrimSpace(cfg.CompatibilityProfilePath),
		ConfigurationID:       strings.TrimSpace(cfg.CompatibilityConfigurationID),
		CompatibilityMode:     strings.TrimSpace(cfg.CompatibilityMode),
		WriteContentType:      strings.TrimSpace(cfg.CompatibilityWriteContentType),
		ReleaseProfileVersion: strings.TrimSpace(cfg.CompatibilityReleaseProfileVersion),
	}
	if input.ConfigurationID == "" {
		input.ConfigurationID = defaultPublicationCompatibilityConfigurationID
	}
	if input.WriteContentType == "" {
		input.WriteContentType = defaultPublicationWriteContentType
	}

	override := publicationPayload
	if raw, ok := publicationPayload["compatibility_profile"].(map[string]interface{}); ok {
		override = raw
	}
	if value := readOptionalString(override["profile_path"]); value != "" {
		input.ProfilePath = value
	}
	if value := readOptionalString(override["configuration_id"]); value != "" {
		input.ConfigurationID = value
	}
	if value := readOptionalString(override["compatibility_mode"]); value != "" {
		input.CompatibilityMode = value
	}
	if value := readOptionalString(override["write_content_type"]); value != "" {
		input.WriteContentType = value
	}
	if value := readOptionalString(override["release_profile_version"]); value != "" {
		input.ReleaseProfileVersion = value
	}
	return input
}

func runPublicationCompatibilityGate(input publicationCompatibilityInput) (*publicationCompatibilityReport, error) {
	profilePath, err := resolveCompatibilityProfilePath(input.ProfilePath)
	if err != nil {
		return nil, err
	}

	profile, err := loadODataCompatibilityProfile(profilePath)
	if err != nil {
		return nil, err
	}

	configurationID := strings.TrimSpace(input.ConfigurationID)
	if configurationID == "" {
		return nil, fmt.Errorf("compatibility profile gate failed: configuration_id is required")
	}

	entry, found := findCompatibilityEntry(profile.Entries, configurationID)
	if !found {
		return nil, fmt.Errorf(
			"compatibility profile gate failed: configuration_id %q is missing in profile",
			configurationID,
		)
	}

	requireApprovedEntry := boolOrDefault(profile.RolloutGate.RequireApprovedEntry, true)
	verificationStatus := strings.ToLower(strings.TrimSpace(entry.VerificationStatus))
	if requireApprovedEntry && verificationStatus != "approved" {
		return nil, fmt.Errorf(
			"compatibility profile gate failed: verification_status=%q for configuration_id=%q",
			entry.VerificationStatus,
			configurationID,
		)
	}

	effectiveWriteContentType := strings.TrimSpace(input.WriteContentType)
	if effectiveWriteContentType == "" {
		effectiveWriteContentType = strings.TrimSpace(entry.MediaTypePolicy.DefaultWriteContentType)
	}
	if !isWriteContentTypeAllowed(
		effectiveWriteContentType,
		normalizeStringSlice(entry.MediaTypePolicy.Accepts),
		normalizeStringSlice(entry.MediaTypePolicy.Rejects),
	) {
		return nil, fmt.Errorf(
			"compatibility profile gate failed: write_content_type %q is incompatible with media_type_policy for configuration_id=%q",
			effectiveWriteContentType,
			configurationID,
		)
	}

	blockOnMediaTypePolicy := boolOrDefault(profile.RolloutGate.BlockOnIncompatibleMediaTypePolicy, true)
	if blockOnMediaTypePolicy &&
		isLegacyModeLE837(input.CompatibilityMode) &&
		!entry.MediaTypePolicy.LegacyModeLE837.Supported {
		note := strings.TrimSpace(entry.MediaTypePolicy.LegacyModeLE837.RequiredPolicyNote)
		if note != "" {
			return nil, fmt.Errorf(
				"compatibility profile gate failed: legacy mode policy blocked for compatibility_mode=%q (%s)",
				input.CompatibilityMode,
				note,
			)
		}
		return nil, fmt.Errorf(
			"compatibility profile gate failed: legacy mode policy blocked for compatibility_mode=%q",
			input.CompatibilityMode,
		)
	}

	profileVersion := strings.TrimSpace(profile.ProfileVersion)
	effectiveReleaseProfileVersion := strings.TrimSpace(input.ReleaseProfileVersion)
	if effectiveReleaseProfileVersion == "" {
		// Keep runtime execution deterministic by pinning to the loaded profile version.
		effectiveReleaseProfileVersion = profileVersion
	}
	requireReleaseProfileVersion := boolOrDefault(profile.RolloutGate.RequireProfileVersionInRelease, true)
	if requireReleaseProfileVersion && effectiveReleaseProfileVersion != profileVersion {
		return nil, fmt.Errorf(
			"compatibility profile gate failed: release_profile_version=%q does not match profile_version=%q",
			effectiveReleaseProfileVersion,
			profileVersion,
		)
	}

	return &publicationCompatibilityReport{
		ProfilePath:           profilePath,
		ProfileVersion:        profileVersion,
		ConfigurationID:       configurationID,
		WriteContentType:      effectiveWriteContentType,
		ReleaseProfileVersion: effectiveReleaseProfileVersion,
	}, nil
}

func loadODataCompatibilityProfile(profilePath string) (*odataCompatibilityProfile, error) {
	raw, err := os.ReadFile(profilePath)
	if err != nil {
		return nil, fmt.Errorf("compatibility profile gate failed: unable to read profile %q: %w", profilePath, err)
	}
	var profile odataCompatibilityProfile
	if err := yaml.Unmarshal(raw, &profile); err != nil {
		return nil, fmt.Errorf("compatibility profile gate failed: invalid yaml %q: %w", profilePath, err)
	}
	if strings.TrimSpace(profile.ProfileVersion) == "" {
		return nil, fmt.Errorf("compatibility profile gate failed: profile_version is missing in %q", profilePath)
	}
	return &profile, nil
}

func resolveCompatibilityProfilePath(configuredPath string) (string, error) {
	candidates := []string{}
	if value := strings.TrimSpace(configuredPath); value != "" {
		candidates = append(candidates, value)
	} else {
		seen := map[string]struct{}{}
		addCandidate := func(value string) {
			clean := filepath.Clean(value)
			if _, exists := seen[clean]; exists {
				return
			}
			seen[clean] = struct{}{}
			candidates = append(candidates, clean)
		}

		addCandidate(defaultPublicationCompatibilityProfilePath)
		if wd, err := os.Getwd(); err == nil {
			base := wd
			for depth := 0; depth < 8; depth++ {
				addCandidate(filepath.Join(base, defaultPublicationCompatibilityProfilePath))
				base = filepath.Join(base, "..")
			}
		}
	}

	for _, candidate := range candidates {
		clean := filepath.Clean(candidate)
		if fileExists(clean) {
			return clean, nil
		}
	}
	return "", fmt.Errorf(
		"compatibility profile gate failed: profile file not found (checked: %s)",
		strings.Join(candidates, ", "),
	)
}

func findCompatibilityEntry(entries []odataCompatibilityEntry, configurationID string) (odataCompatibilityEntry, bool) {
	for _, entry := range entries {
		if strings.TrimSpace(entry.ConfigurationID) == configurationID {
			return entry, true
		}
	}
	return odataCompatibilityEntry{}, false
}

func isWriteContentTypeAllowed(writeContentType string, accepts, rejects []string) bool {
	contentType := strings.TrimSpace(writeContentType)
	if contentType == "" {
		return true
	}
	for _, rejected := range rejects {
		if rejected == contentType {
			return false
		}
	}
	if len(accepts) == 0 {
		return true
	}
	for _, accepted := range accepts {
		if accepted == contentType {
			return true
		}
	}
	return false
}

func isLegacyModeLE837(rawVersion string) bool {
	version := strings.TrimSpace(rawVersion)
	if version == "" {
		return false
	}
	parts := strings.Split(version, ".")
	if len(parts) < 3 {
		return false
	}
	major, errMajor := strconv.Atoi(parts[0])
	minor, errMinor := strconv.Atoi(parts[1])
	patch, errPatch := strconv.Atoi(parts[2])
	if errMajor != nil || errMinor != nil || errPatch != nil {
		return false
	}
	if major < 8 {
		return true
	}
	if major > 8 {
		return false
	}
	if minor < 3 {
		return true
	}
	if minor > 3 {
		return false
	}
	return patch <= 7
}

func normalizeStringSlice(values []string) []string {
	if len(values) == 0 {
		return nil
	}
	out := make([]string, 0, len(values))
	for _, value := range values {
		token := strings.TrimSpace(value)
		if token != "" {
			out = append(out, token)
		}
	}
	return out
}

func boolOrDefault(value *bool, defaultValue bool) bool {
	if value == nil {
		return defaultValue
	}
	return *value
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}
