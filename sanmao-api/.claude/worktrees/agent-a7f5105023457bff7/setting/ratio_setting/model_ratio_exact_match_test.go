package ratio_setting

import "testing"

func TestExactRatioPresenceVsClaudeFallback(t *testing.T) {
	InitRatioSettings()

	if !ContainsExactModelRatio("claude-opus-4-6") {
		t.Fatalf("claude-opus-4-6 should have exact model ratio config")
	}
	if ContainsExactModelRatio("claude-opus-4-8") {
		t.Fatalf("claude-opus-4-8 should not have exact model ratio config")
	}

	got, ok, match := GetModelRatio("claude-opus-4-8")
	if !ok {
		t.Fatalf("claude-opus-4-8 should resolve via fallback")
	}
	if got != 2.5 {
		t.Fatalf("claude-opus-4-8 ratio = %v, want 2.5", got)
	}
	if match != "claude-opus-4-6" {
		t.Fatalf("claude-opus-4-8 matched %s, want claude-opus-4-6", match)
	}

	if ContainsExactCompletionRatio("claude-opus-4-8") {
		t.Fatalf("claude-opus-4-8 should not have exact completion ratio config")
	}
	info := GetCompletionRatioInfo("claude-opus-4-8")
	if !info.Locked || info.Ratio != 5 {
		t.Fatalf("claude-opus-4-8 completion ratio info = %+v, want locked ratio 5", info)
	}
}
