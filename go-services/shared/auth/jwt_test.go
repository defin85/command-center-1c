package auth

import "testing"

func TestValidateTokenAcceptsDjangoSimpleJWTAccessToken(t *testing.T) {
	manager := NewJWTManager(JWTConfig{
		Secret:     "your-jwt-secret-change-in-production",
		ExpireTime: 0,
		Issuer:     "commandcenter1c",
	})

	token := "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." +
		"eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc0ODkxNDUzLCJpYXQiOjE3NzQ4MDUwNTMsImp0aSI6ImE5MjA2YjYxZjM5MTRhZjhhNDhiYTQ2YmVhZTE4ZDYzIiwidXNlcl9pZCI6IjE1IiwidXNlcm5hbWUiOiJjb2RleF9hY2NlcHRhbmNlIiwicm9sZXMiOlsic3RhZmYiXX0." +
		"DxhXrNZRKcTwe-xeofAqQdCjQosb7ZAlSHBapCkKJOY"

	claims, err := manager.ValidateToken(token)
	if err != nil {
		t.Fatalf("ValidateToken() unexpected error: %v", err)
	}
	if claims.UserID != "15" {
		t.Fatalf("ValidateToken() user_id = %q, want %q", claims.UserID, "15")
	}
	if claims.Username != "codex_acceptance" {
		t.Fatalf("ValidateToken() username = %q, want %q", claims.Username, "codex_acceptance")
	}
	if len(claims.Roles) != 1 || claims.Roles[0] != "staff" {
		t.Fatalf("ValidateToken() roles = %#v, want []string{\"staff\"}", claims.Roles)
	}
}
