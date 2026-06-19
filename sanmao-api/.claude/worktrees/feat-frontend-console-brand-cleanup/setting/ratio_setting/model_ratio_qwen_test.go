package ratio_setting

import "testing"

func TestQwenModelRatios(t *testing.T) {
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
			model:           "qwen3.7-plus",
			wantRatio:       0.14285714285714285,
			wantCompletion:  4,
			wantCacheRatio:  0,
			wantExactModel:  true,
			wantExactOutput: true,
		},
		{
			model:           "qwen3.7-max-2026-06-08",
			wantRatio:       0.8571428571428571,
			wantCompletion:  3,
			wantCacheRatio:  0,
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
		if gotCacheRatio, ok := GetCacheRatio(tt.model); ok {
			if gotCacheRatio != tt.wantCacheRatio {
				t.Fatalf("%s cache ratio = %v, want %v", tt.model, gotCacheRatio, tt.wantCacheRatio)
			}
		} else if tt.wantCacheRatio != 0 {
			t.Fatalf("%s expected cache ratio %v", tt.model, tt.wantCacheRatio)
		}
	}
}
