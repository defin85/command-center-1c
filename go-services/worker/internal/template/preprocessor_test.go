package template

import "testing"

func TestPreprocessor_LoopIndex(t *testing.T) {
	p := NewPreprocessor()

	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{"loop.index", "{{ loop.index }}", "{{ forloop.Counter }}"},
		{"loop.index0", "{{ loop.index0 }}", "{{ forloop.Counter0 }}"},
		{"loop.first", "{% if loop.first %}first{% endif %}", "{% if forloop.First %}first{% endif %}"},
		{"loop.last", "{% if loop.last %}last{% endif %}", "{% if forloop.Last %}last{% endif %}"},
		{"loop.length", "{{ loop.length }}", "{{ forloop.Length }}"},
		{"loop.revindex", "{{ loop.revindex }}", "{{ forloop.Revcounter }}"},
		{"loop.revindex0", "{{ loop.revindex0 }}", "{{ forloop.Revcounter0 }}"},
		{"multiple in one", "{{ loop.index }}/{{ loop.length }}", "{{ forloop.Counter }}/{{ forloop.Length }}"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := p.Process(tt.input)
			if result != tt.expected {
				t.Errorf("Process(%q) = %q, want %q", tt.input, result, tt.expected)
			}
		})
	}
}

func TestPreprocessor_CustomTests(t *testing.T) {
	p := NewPreprocessor()

	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{"production_database", "{% if db is production_database %}", "{% if db|is_production_database %}"},
		{"test_database", "{% if db is test_database %}", "{% if db|is_test_database %}"},
		{"development_database", "{% if db is development_database %}", "{% if db|is_development_database %}"},
		{"empty", "{% if items is empty %}", "{% if items|is_empty %}"},
		{"nonempty", "{% if items is nonempty %}", "{% if items|is_nonempty %}"},
		{"with whitespace", "{% if db is  production_database %}", "{% if db|is_production_database %}"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := p.Process(tt.input)
			if result != tt.expected {
				t.Errorf("Process(%q) = %q, want %q", tt.input, result, tt.expected)
			}
		})
	}
}

func TestPreprocessor_NoChange(t *testing.T) {
	p := NewPreprocessor()

	// These should not be changed
	inputs := []struct {
		name  string
		input string
	}{
		{"simple variable", "{{ name }}"},
		{"for loop", "{% for item in items %}{% endfor %}"},
		{"filter", "{{ value|guid1c }}"},
		{"condition", "{% if x == 1 %}{% endif %}"},
		{"forloop already", "{{ forloop.Counter }}"},
		{"partial match loop", "{{ myloop.index }}"}, // Should NOT match - has prefix
	}

	for _, tt := range inputs {
		t.Run(tt.name, func(t *testing.T) {
			result := p.Process(tt.input)
			if result != tt.input {
				t.Errorf("Process(%q) = %q, should not change", tt.input, result)
			}
		})
	}
}

func TestPreprocessor_ProcessRecursive(t *testing.T) {
	p := NewPreprocessor()

	input := map[string]interface{}{
		"filter": "{{ loop.index }}",
		"nested": map[string]interface{}{
			"condition": "{% if loop.first %}{% endif %}",
		},
		"array": []interface{}{
			"{{ loop.last }}",
		},
		"number": 42,
		"bool":   true,
		"nil":    nil,
	}

	result := p.ProcessRecursive(input).(map[string]interface{})

	if result["filter"] != "{{ forloop.Counter }}" {
		t.Errorf("filter not processed correctly: got %v", result["filter"])
	}

	nested := result["nested"].(map[string]interface{})
	if nested["condition"] != "{% if forloop.First %}{% endif %}" {
		t.Errorf("nested condition not processed correctly: got %v", nested["condition"])
	}

	arr := result["array"].([]interface{})
	if arr[0] != "{{ forloop.Last }}" {
		t.Errorf("array element not processed correctly: got %v", arr[0])
	}

	// Non-string values should be unchanged
	if result["number"] != 42 {
		t.Errorf("number changed: got %v", result["number"])
	}
	if result["bool"] != true {
		t.Errorf("bool changed: got %v", result["bool"])
	}
	if result["nil"] != nil {
		t.Errorf("nil changed: got %v", result["nil"])
	}
}

func TestPreprocessor_ComplexTemplate(t *testing.T) {
	p := NewPreprocessor()

	input := `{% for db in databases %}
{% if loop.first %}First item{% endif %}
Item {{ loop.index }} of {{ loop.length }}: {{ db.name }}
{% if db is production_database %}PROD{% endif %}
{% if loop.last %}Last item{% endif %}
{% endfor %}`

	expected := `{% for db in databases %}
{% if forloop.First %}First item{% endif %}
Item {{ forloop.Counter }} of {{ forloop.Length }}: {{ db.name }}
{% if db|is_production_database %}PROD{% endif %}
{% if forloop.Last %}Last item{% endif %}
{% endfor %}`

	result := p.Process(input)
	if result != expected {
		t.Errorf("Complex template not processed correctly.\nGot:\n%s\n\nWant:\n%s", result, expected)
	}
}

func BenchmarkPreprocessor_Process(b *testing.B) {
	p := NewPreprocessor()
	template := `{% for db in databases %}{{ loop.index }}: {{ db.name }}{% if loop.last %} (last){% endif %}{% endfor %}`

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		p.Process(template)
	}
}
