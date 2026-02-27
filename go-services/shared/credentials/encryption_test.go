package credentials

import "testing"

func TestEncryptDecryptCredentials_UnicodeRoundTrip(t *testing.T) {
	transportKey := make([]byte, 32)
	for i := range transportKey {
		transportKey[i] = byte(i + 1)
	}

	source := &DatabaseCredentials{
		DatabaseID: "db-unicode-1",
		ODataURL:   "https://example.test/odata/standard.odata",
		Username:   "ГлавБух",
		Password:   "пароль",
		IBUsername: "ГлавБух",
		IBPassword: "пароль",
	}

	encrypted, err := EncryptCredentials(source, transportKey)
	if err != nil {
		t.Fatalf("EncryptCredentials failed: %v", err)
	}

	decrypted, err := DecryptCredentials(*encrypted, transportKey)
	if err != nil {
		t.Fatalf("DecryptCredentials failed: %v", err)
	}

	if decrypted.Username != source.Username {
		t.Fatalf("Username mismatch: got=%q want=%q", decrypted.Username, source.Username)
	}
	if decrypted.Password != source.Password {
		t.Fatalf("Password mismatch: got=%q want=%q", decrypted.Password, source.Password)
	}
	if decrypted.IBUsername != source.IBUsername {
		t.Fatalf("IBUsername mismatch: got=%q want=%q", decrypted.IBUsername, source.IBUsername)
	}
	if decrypted.IBPassword != source.IBPassword {
		t.Fatalf("IBPassword mismatch: got=%q want=%q", decrypted.IBPassword, source.IBPassword)
	}
}
