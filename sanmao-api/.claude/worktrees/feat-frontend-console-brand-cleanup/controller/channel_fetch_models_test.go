package controller

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/constant"
	"github.com/QuantumNous/new-api/model"
	"github.com/gin-gonic/gin"
)

func TestFetchModelsPassesProxyToGeminiFetcher(t *testing.T) {
	gin.SetMode(gin.TestMode)

	original := fetchGeminiModels
	defer func() {
		fetchGeminiModels = original
	}()

	called := false
	fetchGeminiModels = func(baseURL, apiKey, proxyURL string) ([]string, error) {
		called = true
		if proxyURL != "http://127.0.0.1:17890" {
			t.Fatalf("expected proxy to be passed through, got %q", proxyURL)
		}
		if apiKey != "test-key" {
			t.Fatalf("expected key to be passed through, got %q", apiKey)
		}
		return []string{"gemini-3.1-flash-lite-preview"}, nil
	}

	rec := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(rec)
	ctx.Request = httptest.NewRequest(
		http.MethodPost,
		"/api/channel/fetch_models",
		strings.NewReader(`{"type":24,"key":"test-key","proxy":"http://127.0.0.1:17890"}`),
	)
	ctx.Request.Header.Set("Content-Type", "application/json")

	FetchModels(ctx)

	if !called {
		t.Fatal("expected gemini fetcher to be called")
	}
	if rec.Code != http.StatusOK {
		t.Fatalf("unexpected status code: %d", rec.Code)
	}
	body := rec.Body.String()
	if !strings.Contains(body, `"success":true`) {
		t.Fatalf("expected success response, got %s", body)
	}
	if !strings.Contains(body, "gemini-3.1-flash-lite-preview") {
		t.Fatalf("expected model in response, got %s", body)
	}
}

func TestFetchModelsUsesProviderSpecificUpstreamEndpoints(t *testing.T) {
	gin.SetMode(gin.TestMode)

	cases := []struct {
		name           string
		channelType    int
		baseURL        string
		expectedPath   string
		headerOverride *string
		expectedHeader string
	}{
		{
			name:         "ali compatible models endpoint",
			channelType:  constant.ChannelTypeAli,
			baseURL:      "http://127.0.0.1:18081",
			expectedPath: "/compatible-mode/v1/models",
		},
		{
			name:         "zhipu v4 standard models endpoint",
			channelType:  constant.ChannelTypeZhipu_v4,
			baseURL:      "http://127.0.0.1:18082",
			expectedPath: "/api/paas/v4/models",
		},
		{
			name:           "header override is applied",
			channelType:    constant.ChannelTypeAli,
			baseURL:        "http://127.0.0.1:18083",
			expectedPath:   "/compatible-mode/v1/models",
			headerOverride: common.GetPointer(`{"X-Test-Header":"override-{api_key}"}`),
			expectedHeader: "override-test-key",
		},
	}

	for _, tt := range cases {
		t.Run(tt.name, func(t *testing.T) {
			var gotPath string
			var gotAuth string
			var gotCustom string
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				gotPath = r.URL.Path
				gotAuth = r.Header.Get("Authorization")
				gotCustom = r.Header.Get("X-Test-Header")
				w.Header().Set("Content-Type", "application/json")
				_, _ = w.Write([]byte(`{"data":[{"id":"model-a"},{"id":"model-b"}]}`))
			}))
			defer server.Close()

			rec := httptest.NewRecorder()
			ctx, _ := gin.CreateTestContext(rec)
			body := fmt.Sprintf(`{"type":%d,"key":"test-key","base_url":"%s"`, tt.channelType, server.URL)
			if tt.headerOverride != nil {
				body += fmt.Sprintf(`,"header_override":%s`, *tt.headerOverride)
			}
			body += `}`
			ctx.Request = httptest.NewRequest(http.MethodPost, "/api/channel/fetch_models", strings.NewReader(body))
			ctx.Request.Header.Set("Content-Type", "application/json")

			FetchModels(ctx)

			if rec.Code != http.StatusOK {
				t.Fatalf("unexpected status code: %d", rec.Code)
			}
			if gotPath != tt.expectedPath {
				t.Fatalf("path = %q, want %q", gotPath, tt.expectedPath)
			}
			if gotAuth != "Bearer test-key" {
				t.Fatalf("authorization header = %q, want Bearer test-key", gotAuth)
			}
			if tt.expectedHeader != "" && gotCustom != tt.expectedHeader {
				t.Fatalf("custom header = %q, want %q", gotCustom, tt.expectedHeader)
			}
			if !strings.Contains(rec.Body.String(), "model-a") {
				t.Fatalf("expected response body to include fetched models, got %s", rec.Body.String())
			}
		})
	}
}

func TestFetchChannelUpstreamModelIDsUsesSpecialOpenAIBaseForZhipuPlans(t *testing.T) {
	gin.SetMode(gin.TestMode)

	var gotPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":[{"id":"glm-5.2"}]}`))
	}))
	defer server.Close()

	originalPlan := constant.ChannelSpecialBases["glm-coding-plan"]
	constant.ChannelSpecialBases["glm-coding-plan"] = constant.ChannelSpecialBase{
		ClaudeBaseURL: server.URL + "/api/anthropic",
		OpenAIBaseURL: server.URL + "/api/coding/paas/v4",
	}
	defer func() {
		constant.ChannelSpecialBases["glm-coding-plan"] = originalPlan
	}()

	channel := &model.Channel{
		Type:    constant.ChannelTypeZhipu_v4,
		Key:     "test-key",
		BaseURL: common.GetPointer("glm-coding-plan"),
	}

	ids, err := fetchChannelUpstreamModelIDs(channel)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if gotPath != "/api/coding/paas/v4/models" {
		t.Fatalf("path = %q, want %q", gotPath, "/api/coding/paas/v4/models")
	}
	if len(ids) != 1 || ids[0] != "glm-5.2" {
		t.Fatalf("ids = %v, want [glm-5.2]", ids)
	}
}
