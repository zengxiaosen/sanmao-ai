package common

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadOrCreateSessionSecretPersistsValue(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "session_secret")

	first, err := loadOrCreateSessionSecret(path)
	if err != nil {
		t.Fatalf("first load failed: %v", err)
	}
	if first == "" {
		t.Fatal("expected non-empty secret")
	}

	second, err := loadOrCreateSessionSecret(path)
	if err != nil {
		t.Fatalf("second load failed: %v", err)
	}
	if second != first {
		t.Fatalf("expected persisted secret, got %q then %q", first, second)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read persisted secret failed: %v", err)
	}
	if string(data) != first {
		t.Fatalf("expected file to contain persisted secret %q, got %q", first, string(data))
	}
}
