package edpdata

import "testing"

func TestRedactEmailAndSecret(t *testing.T) {
	in := "user a.b@example.com did token: abc123def456"
	out := redact(in)
	if out == in {
		t.Fatal("redact left the input unchanged")
	}
	if contains(out, "a.b@example.com") {
		t.Errorf("email not redacted: %q", out)
	}
	if contains(out, "abc123def456") {
		t.Errorf("secret not redacted: %q", out)
	}
}

func contains(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
