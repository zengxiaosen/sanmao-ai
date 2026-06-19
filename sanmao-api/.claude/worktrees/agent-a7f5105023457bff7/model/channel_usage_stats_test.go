package model

import (
	"testing"
	"time"

	"github.com/QuantumNous/new-api/common"
	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func setupChannelUsageStatsTestDB(t *testing.T) *gorm.DB {
	t.Helper()

	common.UsingSQLite = true
	common.UsingMySQL = false
	common.UsingPostgreSQL = false

	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to open sqlite db: %v", err)
	}
	DB = db
	LOG_DB = db

	if err := db.AutoMigrate(&Channel{}, &Log{}); err != nil {
		t.Fatalf("failed to migrate tables: %v", err)
	}

	t.Cleanup(func() {
		sqlDB, err := db.DB()
		if err == nil {
			_ = sqlDB.Close()
		}
	})

	return db
}

func TestGetChannelUsageStatsLast24Hours(t *testing.T) {
	db := setupChannelUsageStatsTestDB(t)
	now := time.Now().Unix()

	channels := []*Channel{
		{Id: 1, Name: "yxai-claude", Key: "k1", Status: common.ChannelStatusEnabled},
		{Id: 2, Name: "vision-claude", Key: "k2", Status: common.ChannelStatusEnabled},
		{Id: 3, Name: "gemini-main", Key: "k3", Status: common.ChannelStatusEnabled},
	}
	for _, channel := range channels {
		if err := db.Create(channel).Error; err != nil {
			t.Fatalf("failed to seed channel %d: %v", channel.Id, err)
		}
	}

	logs := []*Log{
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 60,
			ModelName:        "claude-sonnet-4-6",
			ChannelId:        1,
			Quota:            1200,
			PromptTokens:     100,
			CompletionTokens: 50,
		},
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 120,
			ModelName:        "claude-opus-4-6",
			ChannelId:        1,
			Quota:            800,
			PromptTokens:     40,
			CompletionTokens: 10,
		},
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 300,
			ModelName:        "claude-sonnet-4-6",
			ChannelId:        2,
			Quota:            300,
			PromptTokens:     20,
			CompletionTokens: 5,
		},
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 30*3600,
			ModelName:        "claude-sonnet-4-6",
			ChannelId:        2,
			Quota:            999,
			PromptTokens:     999,
			CompletionTokens: 999,
		},
	}
	for _, log := range logs {
		if err := db.Create(log).Error; err != nil {
			t.Fatalf("failed to seed log: %v", err)
		}
	}

	stats, err := GetChannelUsageStats(now - 24*3600)
	if err != nil {
		t.Fatalf("GetChannelUsageStats returned error: %v", err)
	}

	if len(stats) != 2 {
		t.Fatalf("expected 2 channel usage rows, got %d", len(stats))
	}

	if stats[0].ChannelId != 1 {
		t.Fatalf("expected first stats row to be channel 1, got %d", stats[0].ChannelId)
	}
	if stats[0].RequestCount != 2 {
		t.Fatalf("expected channel 1 request count 2, got %d", stats[0].RequestCount)
	}
	if stats[0].Quota != 2000 {
		t.Fatalf("expected channel 1 quota 2000, got %d", stats[0].Quota)
	}
	if stats[0].Tokens != 200 {
		t.Fatalf("expected channel 1 tokens 200, got %d", stats[0].Tokens)
	}

	if stats[1].ChannelId != 2 {
		t.Fatalf("expected second stats row to be channel 2, got %d", stats[1].ChannelId)
	}
	if stats[1].RequestCount != 1 {
		t.Fatalf("expected channel 2 request count 1, got %d", stats[1].RequestCount)
	}
	if stats[1].Quota != 300 {
		t.Fatalf("expected channel 2 quota 300, got %d", stats[1].Quota)
	}
	if stats[1].Tokens != 25 {
		t.Fatalf("expected channel 2 tokens 25, got %d", stats[1].Tokens)
	}
}

func TestGetModelChannelUsageStatsLast24Hours(t *testing.T) {
	db := setupChannelUsageStatsTestDB(t)
	now := time.Now().Unix()

	channels := []*Channel{
		{Id: 1, Name: "yxai-claude", Key: "k1", Status: common.ChannelStatusEnabled},
		{Id: 2, Name: "vision-claude", Key: "k2", Status: common.ChannelStatusEnabled},
	}
	for _, channel := range channels {
		if err := db.Create(channel).Error; err != nil {
			t.Fatalf("failed to seed channel %d: %v", channel.Id, err)
		}
	}

	logs := []*Log{
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 30,
			ModelName:        "claude-sonnet-4-6",
			ChannelId:        1,
			Quota:            500,
			PromptTokens:     50,
			CompletionTokens: 20,
		},
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 45,
			ModelName:        "claude-sonnet-4-6",
			ChannelId:        1,
			Quota:            700,
			PromptTokens:     70,
			CompletionTokens: 30,
		},
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 90,
			ModelName:        "claude-sonnet-4-6",
			ChannelId:        2,
			Quota:            200,
			PromptTokens:     10,
			CompletionTokens: 10,
		},
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 90,
			ModelName:        "claude-opus-4-6",
			ChannelId:        2,
			Quota:            999,
			PromptTokens:     99,
			CompletionTokens: 1,
		},
	}
	for _, log := range logs {
		if err := db.Create(log).Error; err != nil {
			t.Fatalf("failed to seed log: %v", err)
		}
	}

	stats, err := GetModelChannelUsageStats(now-24*3600, "claude-sonnet-4-6")
	if err != nil {
		t.Fatalf("GetModelChannelUsageStats returned error: %v", err)
	}

	if len(stats) != 2 {
		t.Fatalf("expected 2 rows for model stats, got %d", len(stats))
	}
	if stats[0].ChannelId != 1 || stats[0].RequestCount != 2 || stats[0].Quota != 1200 {
		t.Fatalf("unexpected first model stats row: %+v", stats[0])
	}
	if stats[1].ChannelId != 2 || stats[1].RequestCount != 1 || stats[1].Quota != 200 {
		t.Fatalf("unexpected second model stats row: %+v", stats[1])
	}
}

func TestGetChannelModelUsageStatsLast24Hours(t *testing.T) {
	db := setupChannelUsageStatsTestDB(t)
	now := time.Now().Unix()

	channels := []*Channel{
		{Id: 1, Name: "yxai-claude", Key: "k1", Status: common.ChannelStatusEnabled},
		{Id: 2, Name: "vision-claude", Key: "k2", Status: common.ChannelStatusEnabled},
	}
	for _, channel := range channels {
		if err := db.Create(channel).Error; err != nil {
			t.Fatalf("failed to seed channel %d: %v", channel.Id, err)
		}
	}

	logs := []*Log{
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 30,
			ModelName:        "claude-sonnet-4-6",
			ChannelId:        1,
			Quota:            500,
			PromptTokens:     50,
			CompletionTokens: 20,
		},
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 45,
			ModelName:        "claude-haiku-4-5-20251001",
			ChannelId:        1,
			Quota:            100,
			PromptTokens:     10,
			CompletionTokens: 10,
		},
		{
			Type:             LogTypeConsume,
			CreatedAt:        now - 45,
			ModelName:        "claude-opus-4-6",
			ChannelId:        2,
			Quota:            999,
			PromptTokens:     99,
			CompletionTokens: 1,
		},
	}
	for _, log := range logs {
		if err := db.Create(log).Error; err != nil {
			t.Fatalf("failed to seed log: %v", err)
		}
	}

	stats, err := GetChannelModelUsageStats(now-24*3600, 1)
	if err != nil {
		t.Fatalf("GetChannelModelUsageStats returned error: %v", err)
	}

	if len(stats) != 2 {
		t.Fatalf("expected 2 rows for channel model stats, got %d", len(stats))
	}
	if stats[0].ChannelId != 1 || stats[0].ModelName != "claude-sonnet-4-6" {
		t.Fatalf("unexpected first channel model stats row: %+v", stats[0])
	}
	if stats[1].ChannelId != 1 || stats[1].ModelName != "claude-haiku-4-5-20251001" {
		t.Fatalf("unexpected second channel model stats row: %+v", stats[1])
	}
}
