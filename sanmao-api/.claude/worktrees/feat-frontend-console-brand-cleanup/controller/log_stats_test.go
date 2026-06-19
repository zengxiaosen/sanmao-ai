package controller

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/model"
	"github.com/gin-gonic/gin"
	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func setupLogStatsControllerTestDB(t *testing.T) *gorm.DB {
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

	if err := db.AutoMigrate(&model.Channel{}, &model.Log{}); err != nil {
		t.Fatalf("failed to migrate test tables: %v", err)
	}

	t.Cleanup(func() {
		sqlDB, err := db.DB()
		if err == nil {
			_ = sqlDB.Close()
		}
	})

	return db
}

func TestGetChannelUsageStatsReturns24hAggregates(t *testing.T) {
	db := setupLogStatsControllerTestDB(t)
	now := time.Now().Unix()

	requireNoErr := func(err error) {
		t.Helper()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
	}

	requireNoErr(db.Create(&model.Channel{Id: 1, Name: "yxai-claude", Key: "k1", Status: common.ChannelStatusEnabled}).Error)
	requireNoErr(db.Create(&model.Log{
		Type:             model.LogTypeConsume,
		CreatedAt:        now - 60,
		ModelName:        "claude-sonnet-4-6",
		ChannelId:        1,
		Quota:            500,
		PromptTokens:     30,
		CompletionTokens: 20,
	}).Error)

	recorder := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(recorder)
	ctx.Request = httptest.NewRequest(http.MethodGet, "/api/log/channel_usage?window_hours=24", nil)

	GetChannelUsageStats(ctx)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", recorder.Code)
	}
	body := recorder.Body.String()
	if !containsAll(body, []string{"\"success\":true", "\"channel_name\":\"yxai-claude\"", "\"request_count\":1"}) {
		t.Fatalf("unexpected body: %s", body)
	}
}

func TestGetModelChannelUsageStatsFiltersByModel(t *testing.T) {
	db := setupLogStatsControllerTestDB(t)
	now := time.Now().Unix()

	requireNoErr := func(err error) {
		t.Helper()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
	}

	requireNoErr(db.Create(&model.Channel{Id: 1, Name: "yxai-claude", Key: "k1", Status: common.ChannelStatusEnabled}).Error)
	requireNoErr(db.Create(&model.Channel{Id: 2, Name: "vision-claude", Key: "k2", Status: common.ChannelStatusEnabled}).Error)
	requireNoErr(db.Create(&model.Log{
		Type:             model.LogTypeConsume,
		CreatedAt:        now - 60,
		ModelName:        "claude-sonnet-4-6",
		ChannelId:        1,
		Quota:            500,
		PromptTokens:     30,
		CompletionTokens: 20,
	}).Error)
	requireNoErr(db.Create(&model.Log{
		Type:             model.LogTypeConsume,
		CreatedAt:        now - 120,
		ModelName:        "claude-opus-4-6",
		ChannelId:        2,
		Quota:            900,
		PromptTokens:     90,
		CompletionTokens: 10,
	}).Error)

	recorder := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(recorder)
	ctx.Request = httptest.NewRequest(http.MethodGet, "/api/log/model_channel_usage?window_hours=24&model_name=claude-sonnet-4-6", nil)

	GetModelChannelUsageStats(ctx)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", recorder.Code)
	}
	body := recorder.Body.String()
	if !containsAll(body, []string{"\"success\":true", "\"model_name\":\"claude-sonnet-4-6\"", "\"channel_name\":\"yxai-claude\""}) {
		t.Fatalf("unexpected body: %s", body)
	}
	if containsAll(body, []string{"vision-claude"}) {
		t.Fatalf("expected filtered model response to exclude vision-claude, got: %s", body)
	}
}

func TestResolveUsageWindowStartTodayAndWeek(t *testing.T) {
	window, startTimestamp := resolveUsageWindowStart("today")
	if window != "today" {
		t.Fatalf("expected today window, got %s", window)
	}
	if time.Now().Unix()-startTimestamp > 24*3600 {
		t.Fatalf("expected today window start within current day, got %d", startTimestamp)
	}

	window, weekStart := resolveUsageWindowStart("week")
	if window != "week" {
		t.Fatalf("expected week window, got %s", window)
	}
	if weekStart > startTimestamp {
		t.Fatalf("expected week start to be earlier than or equal to today start")
	}
}

func containsAll(text string, parts []string) bool {
	for _, part := range parts {
		if !strings.Contains(text, part) {
			return false
		}
	}
	return true
}
