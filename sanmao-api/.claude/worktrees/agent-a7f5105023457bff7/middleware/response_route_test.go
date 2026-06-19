package middleware

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/model"
	"github.com/gin-gonic/gin"
	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func setupResponseRouteMiddlewareTestDB(t *testing.T) *gorm.DB {
	t.Helper()

	gin.SetMode(gin.TestMode)
	common.UsingSQLite = true
	common.UsingMySQL = false
	common.UsingPostgreSQL = false
	common.RedisEnabled = false

	dsn := fmt.Sprintf("file:%s?mode=memory&cache=shared", t.Name())
	db, err := gorm.Open(sqlite.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to open sqlite db: %v", err)
	}
	model.DB = db
	model.LOG_DB = db

	if err := db.AutoMigrate(&model.Log{}); err != nil {
		t.Fatalf("failed to migrate log table: %v", err)
	}

	t.Cleanup(func() {
		sqlDB, err := db.DB()
		if err == nil {
			_ = sqlDB.Close()
		}
	})

	return db
}

func TestResolveResponseRouteSetsSpecificChannelAndForcedModel(t *testing.T) {
	db := setupResponseRouteMiddlewareTestDB(t)
	if err := db.Create(&model.Log{
		UserId:    1,
		Type:      model.LogTypeConsume,
		ModelName: "gpt-5.4",
		ChannelId: 99,
		Other:     `{"response_id":"resp_123"}`,
	}).Error; err != nil {
		t.Fatalf("failed to seed log: %v", err)
	}

	rec := httptest.NewRecorder()
	router := gin.New()
	router.Use(func(c *gin.Context) {
		c.Set("id", 1)
		c.Next()
	})
	router.GET("/v1/responses/:response_id", ResolveResponseRoute(), func(c *gin.Context) {
		if c.GetString("specific_channel_id") != "99" {
			t.Fatalf("expected specific_channel_id=99, got %q", c.GetString("specific_channel_id"))
		}
		if c.GetString("forced_model_name") != "gpt-5.4" {
			t.Fatalf("expected forced_model_name gpt-5.4, got %q", c.GetString("forced_model_name"))
		}
		c.Status(http.StatusNoContent)
	})

	req := httptest.NewRequest(http.MethodGet, "/v1/responses/resp_123", nil)
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d", rec.Code)
	}
}
