package masking

import "testing"

func TestMaskArgs_MasksDesignerPassword(t *testing.T) {
	got := MaskArgs([]string{"DESIGNER", "/Psecret"})
	if len(got) != 2 {
		t.Fatalf("expected 2 args, got %d", len(got))
	}
	if got[1] != "/P***" {
		t.Fatalf("expected /P***, got %q", got[1])
	}
}

func TestMaskArgs_MasksFlagEquals(t *testing.T) {
	got := MaskArgs([]string{"--password=secret", "--token=abc"})
	if got[0] != "--password=***" {
		t.Fatalf("expected masked password, got %q", got[0])
	}
	if got[1] != "--token=***" {
		t.Fatalf("expected masked token, got %q", got[1])
	}
}

func TestMaskArgs_MasksFlagNextToken(t *testing.T) {
	got := MaskArgs([]string{"--password", "secret", "--other", "x"})
	if len(got) != 4 {
		t.Fatalf("expected 4 args, got %d", len(got))
	}
	if got[0] != "--password" || got[1] != "***" {
		t.Fatalf("expected masked next token, got %q %q", got[0], got[1])
	}
	if got[2] != "--other" || got[3] != "x" {
		t.Fatalf("expected non-sensitive args intact, got %q %q", got[2], got[3])
	}
}
