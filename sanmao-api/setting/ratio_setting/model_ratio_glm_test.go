package ratio_setting

import "testing"

func TestGLMModelRatios(t *testing.T) {
	InitRatioSettings()

	tests := []struct {
		model           string
		wantRatio       float64
		wantCompletion  float64
		wantExactModel  bool
		wantExactOutput bool
	}{
		{
			model:           "glm-5.2",
			wantRatio:       0.4110,
			wantCompletion:  4,
			wantExactModel:  true,
			wantExactOutput: true,
		},
		{
			model:           "glm-5v-turbo",
			wantRatio:       0.3425,
			wantCompletion:  4.4,
			wantExactModel:  true,
			wantExactOutput: true,
		},
		{
			model:           "glm-4.1v-thinking-flashx",
			wantRatio:       0,
			wantCompletion:  4,
			wantExactModel:  true,
			wantExactOutput: true,
		},
	}

	for _, tt := range tests {
		gotRatio, ok, match := GetModelRatio(tt.model)
		if !ok {
			t.Fatalf("%s should resolve exact model ratio", tt.model)
		}
		if gotRatio != tt.wantRatio {
			t.Fatalf("%s ratio = %v, want %v", tt.model, gotRatio, tt.wantRatio)
		}
		if match != tt.model {
			t.Fatalf("%s matched %s, want itself", tt.model, match)
		}
		if ContainsExactModelRatio(tt.model) != tt.wantExactModel {
			t.Fatalf("ContainsExactModelRatio(%s) mismatch", tt.model)
		}
		if gotCompletion := GetCompletionRatio(tt.model); gotCompletion != tt.wantCompletion {
			t.Fatalf("%s completion ratio = %v, want %v", tt.model, gotCompletion, tt.wantCompletion)
		}
		if ContainsExactCompletionRatio(tt.model) != tt.wantExactOutput {
			t.Fatalf("ContainsExactCompletionRatio(%s) mismatch", tt.model)
		}
	}
}
