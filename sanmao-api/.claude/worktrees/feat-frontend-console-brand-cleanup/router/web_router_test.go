package router

import (
	"embed"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

//go:embed testdata/web/dist
var testBuildFS embed.FS

func TestSetWebRouter_ServesIndexForClientRoute(t *testing.T) {
	gin.SetMode(gin.TestMode)
	engine := gin.New()
	indexPage := []byte("<html>index</html>")

	SetWebRouter(engine, testBuildFS, indexPage)

	req := httptest.NewRequest(http.MethodGet, "/pricing", nil)
	rec := httptest.NewRecorder()
	engine.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 for client route, got %d", rec.Code)
	}
	if body := rec.Body.String(); body != string(indexPage) {
		t.Fatalf("expected index page body, got %q", body)
	}
}

func TestSetWebRouter_BlocksSuspiciousFileProbePaths(t *testing.T) {
	gin.SetMode(gin.TestMode)
	engine := gin.New()
	indexPage := []byte("<html>index</html>")

	SetWebRouter(engine, testBuildFS, indexPage)

	probePaths := []string{
		"/.env",
		"/.env.backup",
		"/docker-compose.yaml",
		"/CONTEXT.md",
	}

	for _, path := range probePaths {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		rec := httptest.NewRecorder()
		engine.ServeHTTP(rec, req)

		if rec.Code != http.StatusNotFound {
			t.Fatalf("expected 404 for %s, got %d with body %q", path, rec.Code, rec.Body.String())
		}
	}
}
