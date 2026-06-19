package service

import (
	"testing"

	"github.com/QuantumNous/new-api/types"
)

func TestGetImageTokenUsesGLMVisionFixedCost(t *testing.T) {
	fileMeta := types.NewImageFileMeta(&types.FileSource{Type: types.FileSourceTypeURL, URL: "https://example.com/image.png"}, "high")

	tests := []struct {
		model string
		want  int
	}{
		{model: "glm-4.6v", want: 1047},
		{model: "glm-5v-turbo", want: 1047},
		{model: "glm-4.1v-thinking-flashx", want: 1047},
	}

	for _, tt := range tests {
		got, err := getImageToken(nil, fileMeta, tt.model, true)
		if err != nil {
			t.Fatalf("getImageToken(%q) returned error: %v", tt.model, err)
		}
		if got != tt.want {
			t.Fatalf("getImageToken(%q) = %d, want %d", tt.model, got, tt.want)
		}
	}
}
