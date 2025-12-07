package template

import (
	"regexp"
	"strings"
	"testing"
)

func TestValidator_DangerousPatterns(t *testing.T) {
	v := NewValidator()

	dangerous := []struct {
		name     string
		template string
	}{
		{"dunder class", "{{ __class__ }}"},
		{"dunder globals", "{{ __globals__ }}"},
		{"exec function", "{{ exec('code') }}"},
		{"eval function", "{{ eval(x) }}"},
		{"open function", "{{ open('/etc/passwd') }}"},
		{"import function", "{{ import('os') }}"},
		{"__import__ function", "{{ __import__('sys') }}"},
		{"dunder mro", "{{ obj.__mro__ }}"},
		{"dunder subclasses", "{{ obj.__subclasses__() }}"},
		{"dunder builtins", "{{ __builtins__ }}"},
		{"os module", "{{ os.system('ls') }}"},
		{"sys module", "{{ sys.exit() }}"},
		{"subprocess module", "{{ subprocess.run('ls') }}"},
		{"request module", "{{ request.get('url') }}"},
		{"socket module", "{{ socket.connect() }}"},
		{"compile function", "{{ compile('code', 'file', 'exec') }}"},
		{"func_code access", "{{ func.func_code }}"},
	}

	for _, tc := range dangerous {
		t.Run(tc.name, func(t *testing.T) {
			err := v.Validate(tc.template)
			if err == nil {
				t.Errorf("Validate(%q) should return error for dangerous pattern", tc.template)
			}
			if !IsSecurityError(err) {
				t.Errorf("Validate(%q) should return SecurityError, got %T", tc.template, err)
			}
		})
	}
}

func TestValidator_SafeTemplates(t *testing.T) {
	v := NewValidator()

	safe := []struct {
		name     string
		template string
	}{
		{"simple variable", "{{ name }}"},
		{"for loop", "{% for item in items %}{{ item }}{% endfor %}"},
		{"filter guid1c", "{{ value|guid1c }}"},
		{"if-else", "{% if x == 1 %}yes{% else %}no{% endif %}"},
		{"object property", "{{ user.email }}"},
		{"length filter", "{{ items|length }}"},
		{"nested property", "{{ data.user.name }}"},
		{"with statement", "{% with total=price %}{{ total }}{% endwith %}"},
		{"loop index", "{% for i in items %}{{ forloop.counter }}{% endfor %}"},
		{"date filter", "{{ created|date:'Y-m-d' }}"},
		{"default filter", "{{ value|default:'N/A' }}"},
		{"upper filter", "{{ name|upper }}"},
		{"lower filter", "{{ name|lower }}"},
		{"join filter", "{{ items|join:', ' }}"},
		{"math operations", "{{ count + 1 }}"},
		{"comparison", "{% if count > 0 %}yes{% endif %}"},
	}

	for _, tc := range safe {
		t.Run(tc.name, func(t *testing.T) {
			err := v.Validate(tc.template)
			if err != nil {
				t.Errorf("Validate(%q) should not return error: %v", tc.template, err)
			}
		})
	}
}

func TestValidator_MaxSize(t *testing.T) {
	v := NewValidator()

	// Create template larger than 100KB
	large := strings.Repeat("x", 101*1024)

	err := v.Validate(large)
	if err == nil {
		t.Error("Validate should return error for oversized template")
	}
	if !IsSecurityError(err) {
		t.Errorf("Validate should return SecurityError for oversized template, got %T", err)
	}

	// Template at exactly 100KB should be fine
	exact := strings.Repeat("x", 100*1024)
	err = v.Validate(exact)
	if err != nil {
		t.Errorf("Validate should not return error for 100KB template: %v", err)
	}
}

func TestValidator_CustomMaxSize(t *testing.T) {
	v := NewValidatorWithOptions(WithMaxTemplateSize(1024))

	// 1KB should be fine
	small := strings.Repeat("x", 1024)
	err := v.Validate(small)
	if err != nil {
		t.Errorf("Validate should not return error for 1KB template: %v", err)
	}

	// 2KB should fail
	large := strings.Repeat("x", 2*1024)
	err = v.Validate(large)
	if err == nil {
		t.Error("Validate should return error for 2KB template with 1KB limit")
	}
}

func TestValidator_SafeContext(t *testing.T) {
	v := NewValidator()

	tests := []struct {
		name      string
		ctx       map[string]interface{}
		expectErr bool
	}{
		{
			name:      "private key rejected",
			ctx:       map[string]interface{}{"_private": "value"},
			expectErr: true,
		},
		{
			name:      "dunder key rejected",
			ctx:       map[string]interface{}{"__init__": "value"},
			expectErr: true,
		},
		{
			name:      "underscore prefix rejected",
			ctx:       map[string]interface{}{"_internal_data": "value"},
			expectErr: true,
		},
		{
			name:      "normal keys allowed",
			ctx:       map[string]interface{}{"public": "value", "user": "test"},
			expectErr: false,
		},
		{
			name:      "empty context allowed",
			ctx:       map[string]interface{}{},
			expectErr: false,
		},
		{
			name: "nested normal keys allowed",
			ctx: map[string]interface{}{
				"user":     map[string]interface{}{"name": "test"},
				"database": "mydb",
			},
			expectErr: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			err := v.IsSafeContext(tc.ctx)
			if tc.expectErr && err == nil {
				t.Error("IsSafeContext should return error")
			}
			if !tc.expectErr && err != nil {
				t.Errorf("IsSafeContext should not return error: %v", err)
			}
			if tc.expectErr && err != nil && !IsSecurityError(err) {
				t.Errorf("IsSafeContext should return SecurityError, got %T", err)
			}
		})
	}
}

func TestValidator_ValidateRecursive(t *testing.T) {
	v := NewValidator()

	tests := []struct {
		name      string
		data      interface{}
		expectErr bool
	}{
		{
			name:      "safe string",
			data:      "{{ name }}",
			expectErr: false,
		},
		{
			name:      "dangerous string",
			data:      "{{ __class__ }}",
			expectErr: true,
		},
		{
			name: "safe map",
			data: map[string]interface{}{
				"query": "{{ database }}",
				"user":  "{{ username }}",
			},
			expectErr: false,
		},
		{
			name: "dangerous nested map",
			data: map[string]interface{}{
				"safe":   "{{ name }}",
				"unsafe": "{{ __globals__ }}",
			},
			expectErr: true,
		},
		{
			name:      "safe array",
			data:      []interface{}{"{{ a }}", "{{ b }}", "{{ c }}"},
			expectErr: false,
		},
		{
			name:      "dangerous array",
			data:      []interface{}{"{{ a }}", "{{ exec('code') }}", "{{ c }}"},
			expectErr: true,
		},
		{
			name: "deeply nested safe",
			data: map[string]interface{}{
				"level1": map[string]interface{}{
					"level2": []interface{}{
						"{{ value }}",
					},
				},
			},
			expectErr: false,
		},
		{
			name: "deeply nested dangerous",
			data: map[string]interface{}{
				"level1": map[string]interface{}{
					"level2": []interface{}{
						"{{ __builtins__ }}",
					},
				},
			},
			expectErr: true,
		},
		{
			name:      "non-string values",
			data:      map[string]interface{}{"count": 42, "active": true, "rate": 3.14},
			expectErr: false,
		},
		{
			name:      "nil value",
			data:      nil,
			expectErr: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			err := v.ValidateRecursive(tc.data)
			if tc.expectErr && err == nil {
				t.Error("ValidateRecursive should return error")
			}
			if !tc.expectErr && err != nil {
				t.Errorf("ValidateRecursive should not return error: %v", err)
			}
		})
	}
}

func TestValidator_ValidateAll(t *testing.T) {
	v := NewValidator()

	tests := []struct {
		name        string
		templateStr string
		ctx         map[string]interface{}
		data        interface{}
		expectErr   bool
	}{
		{
			name:        "all valid",
			templateStr: "{{ name }}",
			ctx:         map[string]interface{}{"name": "test"},
			data:        map[string]interface{}{"query": "{{ db }}"},
			expectErr:   false,
		},
		{
			name:        "dangerous template",
			templateStr: "{{ __class__ }}",
			ctx:         map[string]interface{}{"name": "test"},
			data:        nil,
			expectErr:   true,
		},
		{
			name:        "unsafe context",
			templateStr: "{{ name }}",
			ctx:         map[string]interface{}{"_private": "test"},
			data:        nil,
			expectErr:   true,
		},
		{
			name:        "dangerous data",
			templateStr: "{{ name }}",
			ctx:         map[string]interface{}{"name": "test"},
			data:        map[string]interface{}{"query": "{{ eval(x) }}"},
			expectErr:   true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			err := v.ValidateAll(tc.templateStr, tc.ctx, tc.data)
			if tc.expectErr && err == nil {
				t.Error("ValidateAll should return error")
			}
			if !tc.expectErr && err != nil {
				t.Errorf("ValidateAll should not return error: %v", err)
			}
		})
	}
}

func TestValidator_AdditionalPatterns(t *testing.T) {
	// Add custom pattern to block "SECRET" keyword
	customPattern := `SECRET`
	v := NewValidatorWithOptions(
		WithAdditionalPatterns(mustCompileRegexp(customPattern)),
	)

	err := v.Validate("{{ SECRET_KEY }}")
	if err == nil {
		t.Error("Validate should block custom pattern SECRET")
	}

	err = v.Validate("{{ my_SECRET }}")
	if err == nil {
		t.Error("Validate should block custom pattern SECRET in any position")
	}

	// Regular patterns should still work
	err = v.Validate("{{ __class__ }}")
	if err == nil {
		t.Error("Validate should still block default dangerous patterns")
	}

	// Safe templates should still work
	err = v.Validate("{{ name }}")
	if err != nil {
		t.Errorf("Validate should allow safe templates: %v", err)
	}
}

func mustCompileRegexp(pattern string) *regexp.Regexp {
	return regexp.MustCompile(pattern)
}

// Benchmark tests
func BenchmarkValidator_Validate_Simple(b *testing.B) {
	v := NewValidator()
	tmpl := "{{ name }}"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = v.Validate(tmpl)
	}
}

func BenchmarkValidator_Validate_Complex(b *testing.B) {
	v := NewValidator()
	tmpl := `{% for item in items %}
		{{ item.name|upper }} - {{ item.value|default:'N/A' }}
	{% endfor %}`

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = v.Validate(tmpl)
	}
}

func BenchmarkValidator_ValidateRecursive(b *testing.B) {
	v := NewValidator()
	data := map[string]interface{}{
		"query":  "{{ database }}",
		"user":   "{{ username }}",
		"filter": map[string]interface{}{"field": "{{ field }}", "value": "{{ value }}"},
		"items":  []interface{}{"{{ a }}", "{{ b }}", "{{ c }}"},
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = v.ValidateRecursive(data)
	}
}
