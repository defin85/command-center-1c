package codec

import (
	"bytes"
	"testing"
)

// TestPasswordString_Empty проверяет что пустой пароль кодируется как U+FFFD (UTF-8 replacement char)
// Это критично для RAS протокола при Lock/Unlock операциях на базах с пустым DB паролем
func TestPasswordString_Empty(t *testing.T) {
	var buf bytes.Buffer
	enc := NewEncoder()

	enc.PasswordString("", &buf)

	// Ожидаем: NullableSize(3) + UTF-8 replacement char (0xef 0xbf 0xbd)
	// NullableSize(3) = 0x03 (длина 3 байта, 1 байт следует)
	result := buf.Bytes()

	// Проверяем что результат содержит replacement char
	replacementChar := []byte{0xef, 0xbf, 0xbd}
	if !bytes.Contains(result, replacementChar) {
		t.Errorf("Empty password should contain UTF-8 replacement char.\nGot: %x\nWant to contain: %x",
			result, replacementChar)
	}

	// Проверяем что результат имеет корректный размер (1 байт size + 3 байта replacement char = 4)
	if len(result) != 4 {
		t.Errorf("Expected 4 bytes (1 size + 3 replacement), got %d: %x", len(result), result)
	}

	t.Logf("PasswordString(''): %x (correct)", result)
}

// TestPasswordString_NonEmpty проверяет что непустой пароль кодируется обычным образом
func TestPasswordString_NonEmpty(t *testing.T) {
	var buf bytes.Buffer
	enc := NewEncoder()

	password := "test123"
	enc.PasswordString(password, &buf)

	result := buf.Bytes()

	// Проверяем что результат НЕ содержит replacement char
	replacementChar := []byte{0xef, 0xbf, 0xbd}
	if bytes.Contains(result, replacementChar) {
		t.Error("Non-empty password should NOT contain replacement char")
	}

	// Проверяем что результат содержит оригинальный пароль
	if !bytes.Contains(result, []byte(password)) {
		t.Errorf("Password should be preserved in output.\nGot: %x\nWant to contain: %s",
			result, password)
	}

	t.Logf("PasswordString('test123'): %x (correct)", result)
}

// TestPasswordString_VsString сравнивает поведение PasswordString vs String
// Критично чтобы они различались для empty strings!
func TestPasswordString_VsString(t *testing.T) {
	var bufPassword, bufString bytes.Buffer
	enc := NewEncoder()

	// Empty password через PasswordString → U+FFFD
	enc.PasswordString("", &bufPassword)

	// Empty string через String → NULL (0x00)
	enc.String("", &bufString)

	passwordResult := bufPassword.Bytes()
	stringResult := bufString.Bytes()

	// Результаты ДОЛЖНЫ отличаться!
	if bytes.Equal(passwordResult, stringResult) {
		t.Error("PasswordString('') should differ from String('')")
	}

	// PasswordString должен содержать replacement char
	if !bytes.Contains(passwordResult, []byte{0xef, 0xbf, 0xbd}) {
		t.Error("PasswordString('') should contain replacement char")
	}

	// String должен содержать NULL
	if !bytes.Contains(stringResult, []byte{0x00}) {
		t.Error("String('') should contain NULL byte")
	}

	t.Logf("PasswordString(''): %x", passwordResult)
	t.Logf("String(''): %x", stringResult)
}

// TestPasswordString_UTF8Replacement проверяет что используется правильный UTF-8 replacement char
func TestPasswordString_UTF8Replacement(t *testing.T) {
	var buf bytes.Buffer
	enc := NewEncoder()

	enc.PasswordString("", &buf)

	result := buf.Bytes()

	// UTF-8 replacement character (U+FFFD) = 0xEF 0xBF 0xBD
	// Это стандартный replacement char когда encoding invalid
	expectedBytes := []byte{0xef, 0xbf, 0xbd}

	// Проверяем что есть replacement char в output
	if !bytes.Contains(result, expectedBytes) {
		t.Errorf("Expected UTF-8 replacement character 0xEF 0xBF 0xBD in output.\nGot: %x",
			result)
	}
}

// TestPasswordString_RealPasswordVsEmpty проверяет что пароли с контентом работают иначе чем пустые
func TestPasswordString_RealPasswordVsEmpty(t *testing.T) {
	passwords := []string{
		"",
		"postgres",
		"P@ssw0rd!",
		"123456",
		"very-long-password-with-special-chars-!@#$%^&*()",
	}

	var buffers []*bytes.Buffer
	for i := 0; i < len(passwords); i++ {
		buffers = append(buffers, &bytes.Buffer{})
	}

	enc := NewEncoder()

	// Кодируем все пароли
	for i, pwd := range passwords {
		enc.PasswordString(pwd, buffers[i])
	}

	// Проверяем что пустой пароль отличается от всех остальных
	emptyResult := buffers[0].Bytes()
	hasReplacement := bytes.Contains(emptyResult, []byte{0xef, 0xbf, 0xbd})

	for i := 1; i < len(passwords); i++ {
		result := buffers[i].Bytes()
		// Непустые пароли НЕ должны содержать replacement char
		hasReplacementInNonEmpty := bytes.Contains(result, []byte{0xef, 0xbf, 0xbd})

		if passwords[i] != "" && hasReplacementInNonEmpty {
			t.Errorf("Password '%s' should NOT have replacement char", passwords[i])
		}
	}

	if !hasReplacement {
		t.Error("Empty password should have replacement char")
	}

	t.Logf("All passwords encoded correctly")
}

// TestPasswordString_NullableSize проверяет что size кодируется правильно
func TestPasswordString_NullableSize(t *testing.T) {
	var buf bytes.Buffer
	enc := NewEncoder()

	enc.PasswordString("", &buf)

	result := buf.Bytes()

	// Первый байт - это NullableSize(3) для replacement char
	// 3 в NullableSize = 0x03
	if result[0] != 0x03 {
		t.Errorf("First byte should be 0x03 (NullableSize(3)), got 0x%02x", result[0])
	}

	t.Logf("NullableSize encoded correctly: 0x%02x", result[0])
}

// TestPasswordString_LongPassword проверяет что длинные пароли работают корректно
func TestPasswordString_LongPassword(t *testing.T) {
	var buf bytes.Buffer
	enc := NewEncoder()

	// Очень длинный пароль
	longPassword := "very-long-password-" + string(make([]byte, 1000))
	enc.PasswordString(longPassword, &buf)

	result := buf.Bytes()

	// Проверяем что пароль в output
	if !bytes.Contains(result, []byte(longPassword)) {
		t.Errorf("Long password not properly encoded")
	}

	// Проверяем что НЕ replacement char
	if bytes.Contains(result, []byte{0xef, 0xbf, 0xbd}) {
		t.Error("Long password should NOT contain replacement char")
	}
}

// TestPasswordString_SpecialCharacters проверяет пароли со спецсимволами
func TestPasswordString_SpecialCharacters(t *testing.T) {
	specialPasswords := []string{
		"p@ssw0rd!",
		"пароль", // Cyrillic
		"密码",    // Chinese
		"🔐secure", // Emoji
	}

	for _, pwd := range specialPasswords {
		var buf bytes.Buffer
		enc := NewEncoder()

		enc.PasswordString(pwd, &buf)

		result := buf.Bytes()

		// Все непустые пароли НЕ должны содержать replacement char
		if bytes.Contains(result, []byte{0xef, 0xbf, 0xbd}) {
			t.Errorf("Password '%s' should NOT contain replacement char", pwd)
		}

		t.Logf("Special password '%s' encoded correctly", pwd)
	}
}

// BenchmarkPasswordString_Empty бенчмарк для пустого пароля
func BenchmarkPasswordString_Empty(b *testing.B) {
	var buf bytes.Buffer
	enc := NewEncoder()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		buf.Reset()
		enc.PasswordString("", &buf)
	}
}

// BenchmarkPasswordString_NonEmpty бенчмарк для непустого пароля
func BenchmarkPasswordString_NonEmpty(b *testing.B) {
	var buf bytes.Buffer
	enc := NewEncoder()
	password := "postgres123"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		buf.Reset()
		enc.PasswordString(password, &buf)
	}
}

// BenchmarkString_Empty бенчмарк для обычного String с пустым значением
func BenchmarkString_Empty(b *testing.B) {
	var buf bytes.Buffer
	enc := NewEncoder()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		buf.Reset()
		enc.String("", &buf)
	}
}
