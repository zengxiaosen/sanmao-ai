package ratio_setting

import "testing"

func TestDefaultGemini3RatiosAreConfigured(t *testing.T) {
	InitRatioSettings()

	tests := map[string]float64{
		"gemini-3-flash-preview":             4.0,
		"gemini-3.1-flash-lite-preview":      4.0,
		"gemini-3-pro-preview":               6.0,
		"gemini-3.1-pro-preview":             6.0,
		"gemini-3.1-pro-preview-customtools": 6.0,
		"gemini-3-pro-image-preview":         12.0,
		"gemini-3.1-flash-image-preview":     8.0,
	}

	for model, want := range tests {
		got, ok, match := GetModelRatio(model)
		if !ok {
			t.Fatalf("%s should be configured, matched %s with ratio %v", model, match, got)
		}
		if got != want {
			t.Fatalf("%s ratio = %v, want %v", model, got, want)
		}
	}
}
