package ratio_setting

import "testing"

func TestDeepSeekModelRatios(t *testing.T) {
	InitRatioSettings()

	tests := []struct {
		model           string
		wantRatio       float64
		wantCompletion  float64
		wantCacheRatio  float64
		wantExactModel  bool
		wantExactOutput bool
	}{
		{
			model:           "deepseek-v4-pro",
			wantRatio:       0.2175,
			wantCompletion:  2,
			wantCacheRatio:  0.016666666666666666,
			wantExactModel:  true,
			wantExactOutput: true,
		},
		{
			model:           "deepseek-v4-flash",
			wantRatio:       0.07,
			wantCompletion:  2,
			wantCacheRatio:  0.02,
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
		gotCacheRatio, ok := GetCacheRatio(tt.model)
		if !ok {
			t.Fatalf("%s should resolve exact cache ratio", tt.model)
		}
		if gotCacheRatio != tt.wantCacheRatio {
			t.Fatalf("%s cache ratio = %v, want %v", tt.model, gotCacheRatio, tt.wantCacheRatio)
		}
	}
}
