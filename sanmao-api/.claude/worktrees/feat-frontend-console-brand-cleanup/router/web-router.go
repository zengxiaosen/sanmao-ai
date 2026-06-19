package router

import (
	"embed"
	"net/http"
	"path"
	"strings"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/controller"
	"github.com/QuantumNous/new-api/middleware"
	"github.com/gin-contrib/gzip"
	"github.com/gin-contrib/static"
	"github.com/gin-gonic/gin"
)

func isSuspiciousFileProbePath(requestPath string) bool {
	cleanPath := path.Clean("/" + strings.TrimSpace(requestPath))
	base := path.Base(cleanPath)

	if base == "." || base == "/" || base == "" {
		return false
	}

	lowerBase := strings.ToLower(base)
	if strings.HasPrefix(base, ".") {
		return true
	}

	sensitiveSuffixes := []string{
		".env",
		".env.example",
		".env.backup",
		".yaml",
		".yml",
		".toml",
		".ini",
		".conf",
		".log",
		".sql",
		".bak",
		".backup",
		".md",
	}

	for _, suffix := range sensitiveSuffixes {
		if strings.HasSuffix(lowerBase, suffix) {
			return true
		}
	}

	return false
}

func SetWebRouter(router *gin.Engine, buildFS embed.FS, indexPage []byte) {
	router.Use(gzip.Gzip(gzip.DefaultCompression))
	router.Use(middleware.GlobalWebRateLimit())
	router.Use(middleware.Cache())
	router.Use(func(c *gin.Context) {
		requestPath := c.Request.URL.Path
		if strings.HasPrefix(c.Request.RequestURI, "/v1") || strings.HasPrefix(c.Request.RequestURI, "/api") || strings.HasPrefix(c.Request.RequestURI, "/assets") {
			c.Next()
			return
		}
		if isSuspiciousFileProbePath(requestPath) {
			controller.RelayNotFound(c)
			c.Abort()
			return
		}
		c.Next()
	})
	router.Use(static.Serve("/", common.EmbedFolder(buildFS, "web/dist")))
	router.NoRoute(func(c *gin.Context) {
		c.Set(middleware.RouteTagKey, "web")
		requestPath := c.Request.URL.Path
		if strings.HasPrefix(c.Request.RequestURI, "/v1") || strings.HasPrefix(c.Request.RequestURI, "/api") || strings.HasPrefix(c.Request.RequestURI, "/assets") {
			controller.RelayNotFound(c)
			return
		}
		if isSuspiciousFileProbePath(requestPath) {
			controller.RelayNotFound(c)
			return
		}
		c.Header("Cache-Control", "no-cache")
		c.Data(http.StatusOK, "text/html; charset=utf-8", indexPage)
	})
}
