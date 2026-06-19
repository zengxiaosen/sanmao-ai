package ratio_setting

import "testing"

func TestClaudeModelRatioFallbacks(t *testing.T) {
	InitRatioSettings()

	tests := []struct {
		model     string
		wantRatio float64
		wantMatch string
	}{
		{
			model:     "claude-opus-4-7",
			wantRatio: 2.5,
			wantMatch: "claude-opus-4-6",
		},
		{
			model:     "claude-opus-4-8",
			wantRatio: 2.5,
			wantMatch: "claude-opus-4-6",
		},
		{
			model:     "claude-sonnet-4-6-20260101",
			wantRatio: 1.5,
			wantMatch: "claude-sonnet-4-5-20250929",
		},
		{
			model:     "claude-haiku-4-6-20260101",
			wantRatio: 0.5,
			wantMatch: "claude-haiku-4-5-20251001",
		},
	}

	for _, tt := range tests {
		got, ok, match := GetModelRatio(tt.model)
		if !ok {
			t.Fatalf("%s should resolve via fallback", tt.model)
		}
		if got != tt.wantRatio {
			t.Fatalf("%s ratio = %v, want %v", tt.model, got, tt.wantRatio)
		}
		if match != tt.wantMatch {
			t.Fatalf("%s matched %s, want %s", tt.model, match, tt.wantMatch)
		}
	}
}

func TestClaudeCompletionRatioFallbacks(t *testing.T) {
	InitRatioSettings()

	tests := []struct {
		model string
		want  float64
	}{
		{model: "claude-opus-4-7", want: 5},
		{model: "claude-opus-4-8", want: 5},
		{model: "claude-sonnet-4-6-20260101", want: 5},
		{model: "claude-haiku-4-6-20260101", want: 5},
	}

	for _, tt := range tests {
		if got := GetCompletionRatio(tt.model); got != tt.want {
			t.Fatalf("%s completion ratio = %v, want %v", tt.model, got, tt.want)
		}
		info := GetCompletionRatioInfo(tt.model)
		if info.Ratio != tt.want {
			t.Fatalf("%s completion ratio info = %v, want %v", tt.model, info.Ratio, tt.want)
		}
		if !info.Locked {
			t.Fatalf("%s completion ratio info should remain locked", tt.model)
		}
	}
}
