package controller

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/model"
	"github.com/QuantumNous/new-api/setting/operation_setting"
	"github.com/gin-gonic/gin"
	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func setupResponseRouteTestDB(t *testing.T) *gorm.DB {
	t.Helper()

	gin.SetMode(gin.TestMode)
	common.UsingSQLite = true
	common.UsingMySQL = false
	common.UsingPostgreSQL = false
	common.RedisEnabled = false
	operation_setting.SelfUseModeEnabled = true

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

func TestFindResponseRouteInfoByResponseIDReturnsLatestMatch(t *testing.T) {
	db := setupResponseRouteTestDB(t)

	if err := db.Create(&model.Log{
		UserId:    1,
		Type:      model.LogTypeConsume,
		ModelName: "gpt-5.4",
		ChannelId: 11,
		TokenId:   21,
		Group:     "default",
		Other:     `{"response_id":"resp_old"}`,
	}).Error; err != nil {
		t.Fatalf("failed to seed old log: %v", err)
	}
	if err := db.Create(&model.Log{
		UserId:    1,
		Type:      model.LogTypeConsume,
		ModelName: "gpt-5-codex",
		ChannelId: 12,
		TokenId:   22,
		Group:     "local-dev",
		Other:     `{"response_id":"resp_new"}`,
	}).Error; err != nil {
		t.Fatalf("failed to seed new log: %v", err)
	}

	info, err := model.FindResponseRouteInfoByResponseID(1, "resp_new")
	if err != nil {
		t.Fatalf("expected response route info, got error: %v", err)
	}
	if info.ChannelId != 12 || info.ModelName != "gpt-5-codex" || info.TokenId != 22 || info.Group != "local-dev" {
		t.Fatalf("unexpected route info: %+v", info)
	}
}

func TestRelayResponsesByIDReturnsServerErrorWhenForcedModelMissing(t *testing.T) {
	rec := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(rec)
	ctx.Request = httptest.NewRequest(http.MethodGet, "/v1/responses/resp_missing", nil)
	ctx.Params = gin.Params{{Key: "response_id", Value: "resp_missing"}}

	RelayResponsesByID(ctx)

	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500, got %d", rec.Code)
	}
}
