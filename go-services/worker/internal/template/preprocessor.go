package template

import (
	"regexp"
)

// Preprocessor adapts Jinja2 syntax to pongo2.
// pongo2 uses Django-style loop variables (forloop.X) instead of Jinja2 style (loop.X).
// This preprocessor transparently converts templates so users can write Jinja2-compatible syntax.
type Preprocessor struct {
	replacements []replacement
}

type replacement struct {
	pattern *regexp.Regexp
	replace string
}

// NewPreprocessor creates a new preprocessor with default replacements.
func NewPreprocessor() *Preprocessor {
	return &Preprocessor{
		replacements: []replacement{
			// loop.X -> forloop.X conversions (Jinja2 -> Django/pongo2)
			{regexp.MustCompile(`\bloop\.index\b`), "forloop.Counter"},
			{regexp.MustCompile(`\bloop\.index0\b`), "forloop.Counter0"},
			{regexp.MustCompile(`\bloop\.first\b`), "forloop.First"},
			{regexp.MustCompile(`\bloop\.last\b`), "forloop.Last"},
			{regexp.MustCompile(`\bloop\.length\b`), "forloop.Length"},
			{regexp.MustCompile(`\bloop\.revindex\b`), "forloop.Revcounter"},
			{regexp.MustCompile(`\bloop\.revindex0\b`), "forloop.Revcounter0"},

			// Custom tests: ` is production_database` -> `|is_production_database`
			// Jinja2: {% if db is production_database %}
			// pongo2: {% if db|is_production_database %}
			// Note: We capture the space before "is" to avoid leaving trailing space
			{regexp.MustCompile(`\s+is\s+production_database\b`), "|is_production_database"},
			{regexp.MustCompile(`\s+is\s+test_database\b`), "|is_test_database"},
			{regexp.MustCompile(`\s+is\s+development_database\b`), "|is_development_database"},
			{regexp.MustCompile(`\s+is\s+empty\b`), "|is_empty"},
			{regexp.MustCompile(`\s+is\s+nonempty\b`), "|is_nonempty"},
		},
	}
}

// Process applies all replacements to the template string.
func (p *Preprocessor) Process(template string) string {
	result := template
	for _, r := range p.replacements {
		result = r.pattern.ReplaceAllString(result, r.replace)
	}
	return result
}

// ProcessRecursive processes template data recursively.
// This handles nested structures where templates may appear at any level.
func (p *Preprocessor) ProcessRecursive(data interface{}) interface{} {
	switch v := data.(type) {
	case string:
		return p.Process(v)
	case map[string]interface{}:
		result := make(map[string]interface{}, len(v))
		for key, val := range v {
			result[key] = p.ProcessRecursive(val)
		}
		return result
	case []interface{}:
		result := make([]interface{}, len(v))
		for i, item := range v {
			result[i] = p.ProcessRecursive(item)
		}
		return result
	default:
		return data
	}
}
