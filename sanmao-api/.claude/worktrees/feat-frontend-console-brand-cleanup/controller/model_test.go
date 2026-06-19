package controller

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/constant"
	"github.com/QuantumNous/new-api/setting/operation_setting"
	"github.com/gin-gonic/gin"
)

func TestListModelsGeminiReturnsModelsEnvelope(t *testing.T) {
	gin.SetMode(gin.TestMode)
	originalSelfUseMode := operation_setting.SelfUseModeEnabled
	operation_setting.SelfUseModeEnabled = true
	defer func() {
		operation_setting.SelfUseModeEnabled = originalSelfUseMode
	}()

	rec := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(rec)
	ctx.Request = httptest.NewRequest(http.MethodGet, "/v1/models", nil)

	common.SetContextKey(ctx, constant.ContextKeyTokenModelLimitEnabled, true)
	common.SetContextKey(ctx, constant.ContextKeyTokenModelLimit, map[string]bool{
		"gemini-2.0-flash": true,
	})

	ListModels(ctx, constant.ChannelTypeGemini)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}

	var payload struct {
		Models []struct {
			Name string `json:"name"`
		} `json:"models"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if len(payload.Models) != 1 {
		t.Fatalf("expected 1 Gemini model, got %d", len(payload.Models))
	}
	if payload.Models[0].Name != "gemini-2.0-flash" {
		t.Fatalf("expected gemini model name, got %q", payload.Models[0].Name)
	}
}
