package common

import (
	"net/http/httptest"
	"testing"
)

func TestCustomEventWriteContentTypeIncludesCharset(t *testing.T) {
	recorder := httptest.NewRecorder()
	event := CustomEvent{Data: "data: test"}

	event.WriteContentType(recorder)

	if got := recorder.Header().Get("Content-Type"); got != "text/event-stream; charset=utf-8" {
		t.Fatalf("Content-Type = %q, want %q", got, "text/event-stream; charset=utf-8")
	}
	if got := recorder.Header().Get("Cache-Control"); got != "no-cache" {
		t.Fatalf("Cache-Control = %q, want %q", got, "no-cache")
	}
}
