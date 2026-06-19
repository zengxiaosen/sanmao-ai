package helper

import (
	"fmt"
	"net/http/httptest"
	"testing"

	"github.com/QuantumNous/new-api/dto"
	"github.com/gin-gonic/gin"
)

func TestResponseChunkDataWritesDataOnlySSEFrame(t *testing.T) {
	gin.SetMode(gin.TestMode)

	recorder := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(recorder)
	ctx.Request = httptest.NewRequest("GET", "/v1/responses", nil)

	resp := dto.ResponsesStreamResponse{Type: dto.ResponsesOutputTypeItemAdded}
	payload := `{"type":"response.output_item.added"}`

	ResponseChunkData(ctx, resp, payload)

	body := recorder.Body.String()
	if body != fmt.Sprintf("data: %s\n\n", payload) {
		t.Fatalf("body = %q, want %q", body, fmt.Sprintf("data: %s\n\n", payload))
	}
	if got := recorder.Header().Get("Content-Type"); got != "text/event-stream; charset=utf-8" {
		t.Fatalf("Content-Type = %q, want %q", got, "text/event-stream; charset=utf-8")
	}
	if got := recorder.Header().Get("Cache-Control"); got != "no-cache" {
		t.Fatalf("Cache-Control = %q, want %q", got, "no-cache")
	}
}
