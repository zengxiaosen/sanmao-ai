package model

import (
	"context"
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/logger"
	"github.com/QuantumNous/new-api/setting/operation_setting"
	"github.com/QuantumNous/new-api/types"

	"github.com/gin-gonic/gin"

	"github.com/bytedance/gopkg/util/gopool"
	"gorm.io/gorm"
)

type Log struct {
	Id               int    `json:"id" gorm:"index:idx_created_at_id,priority:1;index:idx_user_id_id,priority:2"`
	UserId           int    `json:"user_id" gorm:"index;index:idx_user_id_id,priority:1"`
	CreatedAt        int64  `json:"created_at" gorm:"bigint;index:idx_created_at_id,priority:2;index:idx_created_at_type"`
	Type             int    `json:"type" gorm:"index:idx_created_at_type"`
	Content          string `json:"content"`
	Username         string `json:"username" gorm:"index;index:index_username_model_name,priority:2;default:''"`
	TokenName        string `json:"token_name" gorm:"index;default:''"`
	ModelName        string `json:"model_name" gorm:"index;index:index_username_model_name,priority:1;default:''"`
	Quota            int    `json:"quota" gorm:"default:0"`
	PromptTokens     int    `json:"prompt_tokens" gorm:"default:0"`
	CompletionTokens int    `json:"completion_tokens" gorm:"default:0"`
	UseTime          int    `json:"use_time" gorm:"default:0"`
	IsStream         bool   `json:"is_stream"`
	ChannelId        int    `json:"channel" gorm:"index"`
	ChannelName      string `json:"channel_name" gorm:"->"`
	TokenId          int    `json:"token_id" gorm:"default:0;index"`
	Group            string `json:"group" gorm:"index"`
	Ip               string `json:"ip" gorm:"index;default:''"`
	RequestId        string `json:"request_id,omitempty" gorm:"type:varchar(64);index:idx_logs_request_id;default:''"`
	Other            string `json:"other"`
}

// don't use iota, avoid change log type value
const (
	LogTypeUnknown = 0
	LogTypeTopup   = 1
	LogTypeConsume = 2
	LogTypeManage  = 3
	LogTypeSystem  = 4
	LogTypeError   = 5
	LogTypeRefund  = 6
)

func formatUserLogs(logs []*Log, startIdx int) {
	for i := range logs {
		logs[i].ChannelName = ""
		var otherMap map[string]interface{}
		otherMap, _ = common.StrToMap(logs[i].Other)
		if otherMap != nil {
			// Remove admin-only debug fields.
			delete(otherMap, "admin_info")
			delete(otherMap, "reject_reason")
		}
		logs[i].Other = common.MapToJsonStr(otherMap)
		logs[i].Id = startIdx + i + 1
	}
}

func GetLogByTokenId(tokenId int) (logs []*Log, err error) {
	err = LOG_DB.Model(&Log{}).Where("token_id = ?", tokenId).Order("id desc").Limit(common.MaxRecentItems).Find(&logs).Error
	formatUserLogs(logs, 0)
	return logs, err
}

type ResponseRouteInfo struct {
	ChannelId int
	ModelName string
	TokenId   int
	Group     string
}

func (r *ResponseRouteInfo) ChannelIdString() string {
	if r == nil {
		return ""
	}
	return fmt.Sprintf("%d", r.ChannelId)
}

func FindResponseRouteInfoByResponseID(userId int, responseID string) (*ResponseRouteInfo, error) {
	responseID = strings.TrimSpace(responseID)
	if userId <= 0 || responseID == "" {
		return nil, errors.New("invalid response route lookup input")
	}

	var logs []*Log
	if err := LOG_DB.Where("user_id = ? AND type = ? AND other LIKE ?", userId, LogTypeConsume, "%\"response_id\":\""+responseID+"\"%").
		Order("id desc").
		Limit(20).
		Find(&logs).Error; err != nil {
		return nil, err
	}

	for _, entry := range logs {
		if entry == nil || entry.Other == "" {
			continue
		}
		otherMap, err := common.StrToMap(entry.Other)
		if err != nil || otherMap == nil {
			continue
		}
		if common.Interface2String(otherMap["response_id"]) != responseID {
			continue
		}
		if entry.ChannelId == 0 || strings.TrimSpace(entry.ModelName) == "" {
			return nil, fmt.Errorf("response route info for %s is incomplete", responseID)
		}
		return &ResponseRouteInfo{
			ChannelId: entry.ChannelId,
			ModelName: entry.ModelName,
			TokenId:   entry.TokenId,
			Group:     entry.Group,
		}, nil
	}
	return nil, gorm.ErrRecordNotFound
}

func RecordLog(userId int, logType int, content string) {
	if logType == LogTypeConsume && !common.LogConsumeEnabled {
		return
	}
	username, _ := GetUsernameById(userId, false)
	log := &Log{
		UserId:    userId,
		Username:  username,
		CreatedAt: common.GetTimestamp(),
		Type:      logType,
		Content:   content,
	}
	err := LOG_DB.Create(log).Error
	if err != nil {
		common.SysLog("failed to record log: " + err.Error())
	}
}

func RecordErrorLog(c *gin.Context, userId int, channelId int, modelName string, tokenName string, content string, tokenId int, useTimeSeconds int,
	isStream bool, group string, other map[string]interface{}) {
	logger.LogInfo(c, fmt.Sprintf("record error log: userId=%d, channelId=%d, modelName=%s, tokenName=%s, content=%s", userId, channelId, modelName, tokenName, content))
	username := c.GetString("username")
	requestId := c.GetString(common.RequestIdKey)
	otherStr := common.MapToJsonStr(other)
	// 判断是否需要记录 IP
	needRecordIp := false
	if settingMap, err := GetUserSetting(userId, false); err == nil {
		if settingMap.RecordIpLog {
			needRecordIp = true
		}
	}
	log := &Log{
		UserId:           userId,
		Username:         username,
		CreatedAt:        common.GetTimestamp(),
		Type:             LogTypeError,
		Content:          content,
		PromptTokens:     0,
		CompletionTokens: 0,
		TokenName:        tokenName,
		ModelName:        modelName,
		Quota:            0,
		ChannelId:        channelId,
		TokenId:          tokenId,
		UseTime:          useTimeSeconds,
		IsStream:         isStream,
		Group:            group,
		Ip: func() string {
			if needRecordIp {
				return c.ClientIP()
			}
			return ""
		}(),
		RequestId: requestId,
		Other:     otherStr,
	}
	err := LOG_DB.Create(log).Error
	if err != nil {
		logger.LogError(c, "failed to record log: "+err.Error())
	}
}

type RecordConsumeLogParams struct {
	ChannelId        int                    `json:"channel_id"`
	PromptTokens     int                    `json:"prompt_tokens"`
	CompletionTokens int                    `json:"completion_tokens"`
	ModelName        string                 `json:"model_name"`
	TokenName        string                 `json:"token_name"`
	Quota            int                    `json:"quota"`
	Content          string                 `json:"content"`
	TokenId          int                    `json:"token_id"`
	UseTimeSeconds   int                    `json:"use_time_seconds"`
	IsStream         bool                   `json:"is_stream"`
	Group            string                 `json:"group"`
	Other            map[string]interface{} `json:"other"`
}

func RecordConsumeLog(c *gin.Context, userId int, params RecordConsumeLogParams) {
	if !common.LogConsumeEnabled {
		return
	}
	logger.LogInfo(c, fmt.Sprintf("record consume log: userId=%d, params=%s", userId, common.GetJsonString(params)))
	username := c.GetString("username")
	requestId := c.GetString(common.RequestIdKey)
	otherStr := common.MapToJsonStr(params.Other)
	// 判断是否需要记录 IP
	needRecordIp := false
	if settingMap, err := GetUserSetting(userId, false); err == nil {
		if settingMap.RecordIpLog {
			needRecordIp = true
		}
	}
	log := &Log{
		UserId:           userId,
		Username:         username,
		CreatedAt:        common.GetTimestamp(),
		Type:             LogTypeConsume,
		Content:          params.Content,
		PromptTokens:     params.PromptTokens,
		CompletionTokens: params.CompletionTokens,
		TokenName:        params.TokenName,
		ModelName:        params.ModelName,
		Quota:            params.Quota,
		ChannelId:        params.ChannelId,
		TokenId:          params.TokenId,
		UseTime:          params.UseTimeSeconds,
		IsStream:         params.IsStream,
		Group:            params.Group,
		Ip: func() string {
			if needRecordIp {
				return c.ClientIP()
			}
			return ""
		}(),
		RequestId: requestId,
		Other:     otherStr,
	}
	err := LOG_DB.Create(log).Error
	if err != nil {
		logger.LogError(c, "failed to record log: "+err.Error())
	}
	if common.DataExportEnabled {
		gopool.Go(func() {
			LogQuotaData(userId, username, params.ModelName, params.Quota, common.GetTimestamp(), params.PromptTokens+params.CompletionTokens)
		})
	}
}

type RecordTaskBillingLogParams struct {
	UserId    int
	LogType   int
	Content   string
	ChannelId int
	ModelName string
	Quota     int
	TokenId   int
	Group     string
	Other     map[string]interface{}
}

func RecordTaskBillingLog(params RecordTaskBillingLogParams) {
	if params.LogType == LogTypeConsume && !common.LogConsumeEnabled {
		return
	}
	username, _ := GetUsernameById(params.UserId, false)
	tokenName := ""
	if params.TokenId > 0 {
		if token, err := GetTokenById(params.TokenId); err == nil {
			tokenName = token.Name
		}
	}
	log := &Log{
		UserId:    params.UserId,
		Username:  username,
		CreatedAt: common.GetTimestamp(),
		Type:      params.LogType,
		Content:   params.Content,
		TokenName: tokenName,
		ModelName: params.ModelName,
		Quota:     params.Quota,
		ChannelId: params.ChannelId,
		TokenId:   params.TokenId,
		Group:     params.Group,
		Other:     common.MapToJsonStr(params.Other),
	}
	err := LOG_DB.Create(log).Error
	if err != nil {
		common.SysLog("failed to record task billing log: " + err.Error())
	}
}

func GetAllLogs(logType int, startTimestamp int64, endTimestamp int64, modelName string, username string, tokenName string, startIdx int, num int, channel int, group string, requestId string) (logs []*Log, total int64, err error) {
	var tx *gorm.DB
	if logType == LogTypeUnknown {
		tx = LOG_DB
	} else {
		tx = LOG_DB.Where("logs.type = ?", logType)
	}

	if modelName != "" {
		tx = tx.Where("logs.model_name like ?", modelName)
	}
	if username != "" {
		tx = tx.Where("logs.username = ?", username)
	}
	if tokenName != "" {
		tx = tx.Where("logs.token_name = ?", tokenName)
	}
	if requestId != "" {
		tx = tx.Where("logs.request_id = ?", requestId)
	}
	if startTimestamp != 0 {
		tx = tx.Where("logs.created_at >= ?", startTimestamp)
	}
	if endTimestamp != 0 {
		tx = tx.Where("logs.created_at <= ?", endTimestamp)
	}
	if channel != 0 {
		tx = tx.Where("logs.channel_id = ?", channel)
	}
	if group != "" {
		tx = tx.Where("logs."+logGroupCol+" = ?", group)
	}
	err = tx.Model(&Log{}).Count(&total).Error
	if err != nil {
		return nil, 0, err
	}
	err = tx.Order("logs.id desc").Limit(num).Offset(startIdx).Find(&logs).Error
	if err != nil {
		return nil, 0, err
	}

	channelIds := types.NewSet[int]()
	for _, log := range logs {
		if log.ChannelId != 0 {
			channelIds.Add(log.ChannelId)
		}
	}

	if channelIds.Len() > 0 {
		var channels []struct {
			Id   int    `gorm:"column:id"`
			Name string `gorm:"column:name"`
		}
		if common.MemoryCacheEnabled {
			// Cache get channel
			for _, channelId := range channelIds.Items() {
				if cacheChannel, err := CacheGetChannel(channelId); err == nil {
					channels = append(channels, struct {
						Id   int    `gorm:"column:id"`
						Name string `gorm:"column:name"`
					}{
						Id:   channelId,
						Name: cacheChannel.Name,
					})
				}
			}
		} else {
			// Bulk query channels from DB
			if err = DB.Table("channels").Select("id, name").Where("id IN ?", channelIds.Items()).Find(&channels).Error; err != nil {
				return logs, total, err
			}
		}
		channelMap := make(map[int]string, len(channels))
		for _, channel := range channels {
			channelMap[channel.Id] = channel.Name
		}
		for i := range logs {
			logs[i].ChannelName = channelMap[logs[i].ChannelId]
		}
	}

	return logs, total, err
}

const logSearchCountLimit = 10000

func GetUserLogs(userId int, logType int, startTimestamp int64, endTimestamp int64, modelName string, tokenName string, startIdx int, num int, group string, requestId string) (logs []*Log, total int64, err error) {
	var tx *gorm.DB
	if logType == LogTypeUnknown {
		tx = LOG_DB.Where("logs.user_id = ?", userId)
	} else {
		tx = LOG_DB.Where("logs.user_id = ? and logs.type = ?", userId, logType)
	}

	if modelName != "" {
		modelNamePattern, err := sanitizeLikePattern(modelName)
		if err != nil {
			return nil, 0, err
		}
		tx = tx.Where("logs.model_name LIKE ? ESCAPE '!'", modelNamePattern)
	}
	if tokenName != "" {
		tx = tx.Where("logs.token_name = ?", tokenName)
	}
	if requestId != "" {
		tx = tx.Where("logs.request_id = ?", requestId)
	}
	if startTimestamp != 0 {
		tx = tx.Where("logs.created_at >= ?", startTimestamp)
	}
	if endTimestamp != 0 {
		tx = tx.Where("logs.created_at <= ?", endTimestamp)
	}
	if group != "" {
		tx = tx.Where("logs."+logGroupCol+" = ?", group)
	}
	err = tx.Model(&Log{}).Limit(logSearchCountLimit).Count(&total).Error
	if err != nil {
		common.SysError("failed to count user logs: " + err.Error())
		return nil, 0, errors.New("查询日志失败")
	}
	err = tx.Order("logs.id desc").Limit(num).Offset(startIdx).Find(&logs).Error
	if err != nil {
		common.SysError("failed to search user logs: " + err.Error())
		return nil, 0, errors.New("查询日志失败")
	}

	formatUserLogs(logs, startIdx)
	return logs, total, err
}

type Stat struct {
	Quota                int     `json:"quota"`
	Rpm                  int     `json:"rpm"`
	Tpm                  int     `json:"tpm"`
	Count                int     `json:"count" gorm:"column:count"`
	Tokens               int     `json:"tokens" gorm:"column:tokens"`
	UpstreamCostQuota    int     `json:"upstream_cost_quota"`
	UsageCostQuota       int     `json:"usage_cost_quota"`
	FixedCostQuota       int     `json:"fixed_cost_quota"`
	NetProfitQuota       int     `json:"net_profit_quota"`
	ProfitRate           float64 `json:"profit_rate"`
	CostConfigured       bool    `json:"cost_configured"`
	CostConfiguredLogs   int     `json:"cost_configured_logs"`
	CostUnconfiguredLogs int     `json:"cost_unconfigured_logs"`
}

type BusinessCostModelConfig struct {
	InputPerMillion  float64 `json:"input_per_million"`
	OutputPerMillion float64 `json:"output_per_million"`
	RequestCost      float64 `json:"request_cost,omitempty"`
}

type BusinessCostChannelConfig struct {
	Default *BusinessCostModelConfig           `json:"default,omitempty"`
	Models  map[string]BusinessCostModelConfig `json:"models,omitempty"`
}

type BusinessFixedCostConfig struct {
	Name           string  `json:"name"`
	Amount         float64 `json:"amount"`
	Currency       string  `json:"currency"`
	Period         string  `json:"period"`
	StartTimestamp int64   `json:"start_timestamp,omitempty"`
	EndTimestamp   int64   `json:"end_timestamp,omitempty"`
	ChannelIDs     []int   `json:"channel_ids,omitempty"`
}

type BusinessCostConfig struct {
	Channels   map[string]BusinessCostChannelConfig `json:"channels,omitempty"`
	FixedCosts []BusinessFixedCostConfig            `json:"fixed_costs,omitempty"`
}

type ChannelUsageStat struct {
	ChannelId     int    `json:"channel_id" gorm:"column:channel_id"`
	ChannelName   string `json:"channel_name" gorm:"column:channel_name"`
	RequestCount  int    `json:"request_count" gorm:"column:request_count"`
	Quota         int    `json:"quota" gorm:"column:quota"`
	Tokens        int    `json:"tokens" gorm:"column:tokens"`
	LastRequestAt int64  `json:"last_request_at" gorm:"column:last_request_at"`
	ModelName     string `json:"model_name,omitempty" gorm:"column:model_name"`
}

func GetChannelUsageStats(startTimestamp int64) ([]*ChannelUsageStat, error) {
	stats := make([]*ChannelUsageStat, 0)
	tx := LOG_DB.Table("logs").
		Select(
			"logs.channel_id as channel_id, channels.name as channel_name, count(*) as request_count, "+
				"coalesce(sum(logs.quota), 0) as quota, "+
				"coalesce(sum(logs.prompt_tokens) + sum(logs.completion_tokens), 0) as tokens, "+
				"max(logs.created_at) as last_request_at",
		).
		Joins("LEFT JOIN channels ON channels.id = logs.channel_id").
		Where("logs.type = ?", LogTypeConsume).
		Where("logs.channel_id != 0")
	if startTimestamp > 0 {
		tx = tx.Where("logs.created_at >= ?", startTimestamp)
	}
	err := tx.Group("logs.channel_id, channels.name").
		Order("quota DESC, request_count DESC, logs.channel_id ASC").
		Scan(&stats).Error
	return stats, err
}

func GetModelChannelUsageStats(startTimestamp int64, modelName string) ([]*ChannelUsageStat, error) {
	stats := make([]*ChannelUsageStat, 0)
	tx := LOG_DB.Table("logs").
		Select(
			"logs.model_name as model_name, logs.channel_id as channel_id, channels.name as channel_name, count(*) as request_count, "+
				"coalesce(sum(logs.quota), 0) as quota, "+
				"coalesce(sum(logs.prompt_tokens) + sum(logs.completion_tokens), 0) as tokens, "+
				"max(logs.created_at) as last_request_at",
		).
		Joins("LEFT JOIN channels ON channels.id = logs.channel_id").
		Where("logs.type = ?", LogTypeConsume).
		Where("logs.channel_id != 0")
	if startTimestamp > 0 {
		tx = tx.Where("logs.created_at >= ?", startTimestamp)
	}
	if modelName != "" {
		tx = tx.Where("logs.model_name = ?", modelName)
	}
	err := tx.Group("logs.model_name, logs.channel_id, channels.name").
		Order("quota DESC, request_count DESC, logs.channel_id ASC").
		Scan(&stats).Error
	return stats, err
}

func GetChannelModelUsageStats(startTimestamp int64, channelID int) ([]*ChannelUsageStat, error) {
	stats := make([]*ChannelUsageStat, 0)
	tx := LOG_DB.Table("logs").
		Select(
			"logs.model_name as model_name, logs.channel_id as channel_id, channels.name as channel_name, count(*) as request_count, "+
				"coalesce(sum(logs.quota), 0) as quota, "+
				"coalesce(sum(logs.prompt_tokens) + sum(logs.completion_tokens), 0) as tokens, "+
				"max(logs.created_at) as last_request_at",
		).
		Joins("LEFT JOIN channels ON channels.id = logs.channel_id").
		Where("logs.type = ?", LogTypeConsume).
		Where("logs.channel_id != 0")
	if startTimestamp > 0 {
		tx = tx.Where("logs.created_at >= ?", startTimestamp)
	}
	if channelID > 0 {
		tx = tx.Where("logs.channel_id = ?", channelID)
	}
	err := tx.Group("logs.model_name, logs.channel_id, channels.name").
		Order("quota DESC, request_count DESC, logs.model_name ASC").
		Scan(&stats).Error
	return stats, err
}

func SumUsedQuota(logType int, startTimestamp int64, endTimestamp int64, modelName string, username string, tokenName string, channel int, group string) (stat Stat, err error) {
	tx := LOG_DB.Table("logs").Select(
		"coalesce(sum(quota), 0) quota, count(*) count, coalesce(sum(prompt_tokens) + sum(completion_tokens), 0) tokens",
	)

	// 为rpm和tpm创建单独的查询
	rpmTpmQuery := LOG_DB.Table("logs").Select(
		"count(*) rpm, coalesce(sum(prompt_tokens) + sum(completion_tokens), 0) tpm",
	)

	if username != "" {
		tx = tx.Where("username = ?", username)
		rpmTpmQuery = rpmTpmQuery.Where("username = ?", username)
	}
	if tokenName != "" {
		tx = tx.Where("token_name = ?", tokenName)
		rpmTpmQuery = rpmTpmQuery.Where("token_name = ?", tokenName)
	}
	if startTimestamp != 0 {
		tx = tx.Where("created_at >= ?", startTimestamp)
	}
	if endTimestamp != 0 {
		tx = tx.Where("created_at <= ?", endTimestamp)
	}
	if modelName != "" {
		modelNamePattern, err := sanitizeLikePattern(modelName)
		if err != nil {
			return stat, err
		}
		tx = tx.Where("model_name LIKE ? ESCAPE '!'", modelNamePattern)
		rpmTpmQuery = rpmTpmQuery.Where("model_name LIKE ? ESCAPE '!'", modelNamePattern)
	}
	if channel != 0 {
		tx = tx.Where("channel_id = ?", channel)
		rpmTpmQuery = rpmTpmQuery.Where("channel_id = ?", channel)
	}
	if group != "" {
		tx = tx.Where(logGroupCol+" = ?", group)
		rpmTpmQuery = rpmTpmQuery.Where(logGroupCol+" = ?", group)
	}

	tx = tx.Where("type = ?", LogTypeConsume)
	rpmTpmQuery = rpmTpmQuery.Where("type = ?", LogTypeConsume)

	// 只统计最近60秒的rpm和tpm
	rpmTpmQuery = rpmTpmQuery.Where("created_at >= ?", time.Now().Add(-60*time.Second).Unix())

	// 执行查询
	if err := tx.Scan(&stat).Error; err != nil {
		common.SysError("failed to query log stat: " + err.Error())
		return stat, errors.New("查询统计数据失败")
	}
	if err := rpmTpmQuery.Scan(&stat).Error; err != nil {
		common.SysError("failed to query rpm/tpm stat: " + err.Error())
		return stat, errors.New("查询统计数据失败")
	}

	if logType == LogTypeConsume {
		if err := fillBusinessCostStat(&stat, startTimestamp, endTimestamp, modelName, username, tokenName, channel, group); err != nil {
			common.SysError("failed to query business cost stat: " + err.Error())
			return stat, errors.New("查询经营成本统计失败")
		}
	}

	return stat, nil
}

func GetBusinessCostConfig() BusinessCostConfig {
	config := BusinessCostConfig{}
	common.OptionMapRWMutex.RLock()
	raw := common.OptionMap["BusinessCostConfig"]
	common.OptionMapRWMutex.RUnlock()
	if strings.TrimSpace(raw) == "" {
		return config
	}
	if err := common.UnmarshalJsonStr(raw, &config); err != nil {
		common.SysError("failed to parse BusinessCostConfig: " + err.Error())
		return BusinessCostConfig{}
	}
	return config
}

func resolveBusinessCostModel(config BusinessCostConfig, channelID int, modelName string) (BusinessCostModelConfig, bool) {
	channelConfig, ok := config.Channels[strconv.Itoa(channelID)]
	if !ok {
		return BusinessCostModelConfig{}, false
	}
	if modelConfig, ok := channelConfig.Models[modelName]; ok {
		return modelConfig, true
	}
	if channelConfig.Default != nil {
		return *channelConfig.Default, true
	}
	return BusinessCostModelConfig{}, false
}

func IsBusinessCostConfigEnabled(config BusinessCostConfig) bool {
	return len(config.Channels) > 0 || len(config.FixedCosts) > 0
}

func HasBusinessCostForChannelModel(config BusinessCostConfig, channelID int, modelName string) bool {
	if !IsBusinessCostConfigEnabled(config) {
		return true
	}
	if _, ok := resolveBusinessCostModel(config, channelID, modelName); ok {
		return true
	}
	for _, cost := range config.FixedCosts {
		if cost.Amount > 0 && fixedCostBoundToChannel(cost, channelID) {
			return true
		}
	}
	return false
}

func getBusinessCostWindow(startTimestamp int64, endTimestamp int64) (int64, int64) {
	if startTimestamp <= 0 && endTimestamp <= 0 {
		now := time.Now()
		return time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, now.Location()).Unix(), now.Unix()
	}
	if startTimestamp <= 0 {
		return endTimestamp, endTimestamp
	}
	if endTimestamp <= 0 || endTimestamp < startTimestamp {
		endTimestamp = time.Now().Unix()
	}
	return startTimestamp, endTimestamp
}

func businessFixedCostPeriodSeconds(period string) float64 {
	switch strings.ToLower(strings.TrimSpace(period)) {
	case "hour", "hourly":
		return 60 * 60
	case "day", "daily":
		return 24 * 60 * 60
	case "year", "yearly":
		return 365 * 24 * 60 * 60
	default:
		return 30 * 24 * 60 * 60
	}
}

func businessFixedCostToUSD(cost BusinessFixedCostConfig) float64 {
	switch strings.ToUpper(strings.TrimSpace(cost.Currency)) {
	case "USD", "":
		return cost.Amount
	case "CNY", "RMB":
		if operation_setting.USDExchangeRate <= 0 {
			return 0
		}
		return cost.Amount / operation_setting.USDExchangeRate
	default:
		return cost.Amount
	}
}

func fixedCostAppliesToChannel(cost BusinessFixedCostConfig, channel int) bool {
	if channel == 0 || len(cost.ChannelIDs) == 0 {
		return true
	}
	for _, channelID := range cost.ChannelIDs {
		if channelID == channel {
			return true
		}
	}
	return false
}

func fixedCostBoundToChannel(cost BusinessFixedCostConfig, channel int) bool {
	if channel == 0 || len(cost.ChannelIDs) == 0 {
		return false
	}
	for _, channelID := range cost.ChannelIDs {
		if channelID == channel {
			return true
		}
	}
	return false
}

func calculateFixedCostUSD(config BusinessCostConfig, startTimestamp int64, endTimestamp int64, channel int) float64 {
	if len(config.FixedCosts) == 0 {
		return 0
	}
	start, end := getBusinessCostWindow(startTimestamp, endTimestamp)
	if end <= start {
		return 0
	}
	duration := float64(end - start)
	var total float64
	for _, cost := range config.FixedCosts {
		if cost.Amount <= 0 || !fixedCostAppliesToChannel(cost, channel) {
			continue
		}
		costStart := cost.StartTimestamp
		costEnd := cost.EndTimestamp
		if costStart > 0 && costEnd > costStart {
			overlapStart := start
			if costStart > overlapStart {
				overlapStart = costStart
			}
			overlapEnd := end
			if costEnd < overlapEnd {
				overlapEnd = costEnd
			}
			if overlapEnd <= overlapStart {
				continue
			}
			total += businessFixedCostToUSD(cost) * float64(overlapEnd-overlapStart) / float64(costEnd-costStart)
			continue
		}
		periodSeconds := businessFixedCostPeriodSeconds(cost.Period)
		if periodSeconds <= 0 {
			continue
		}
		total += businessFixedCostToUSD(cost) * duration / periodSeconds
	}
	return total
}

func fillBusinessCostStat(stat *Stat, startTimestamp int64, endTimestamp int64, modelName string, username string, tokenName string, channel int, group string) error {
	costConfig := GetBusinessCostConfig()
	if !IsBusinessCostConfigEnabled(costConfig) {
		stat.CostConfigured = false
		stat.CostUnconfiguredLogs = stat.Count
		return nil
	}

	logs := make([]Log, 0)
	tx := LOG_DB.Table("logs").Select("channel_id, model_name, prompt_tokens, completion_tokens")
	if username != "" {
		tx = tx.Where("username = ?", username)
	}
	if tokenName != "" {
		tx = tx.Where("token_name = ?", tokenName)
	}
	if startTimestamp != 0 {
		tx = tx.Where("created_at >= ?", startTimestamp)
	}
	if endTimestamp != 0 {
		tx = tx.Where("created_at <= ?", endTimestamp)
	}
	if modelName != "" {
		modelNamePattern, err := sanitizeLikePattern(modelName)
		if err != nil {
			return err
		}
		tx = tx.Where("model_name LIKE ? ESCAPE '!'", modelNamePattern)
	}
	if channel != 0 {
		tx = tx.Where("channel_id = ?", channel)
	}
	if group != "" {
		tx = tx.Where(logGroupCol+" = ?", group)
	}
	if err := tx.Where("type = ?", LogTypeConsume).Find(&logs).Error; err != nil {
		return err
	}

	var usageCostUSD float64
	for _, log := range logs {
		modelCost, ok := resolveBusinessCostModel(costConfig, log.ChannelId, log.ModelName)
		if !ok {
			stat.CostUnconfiguredLogs++
			continue
		}
		stat.CostConfiguredLogs++
		usageCostUSD += float64(log.PromptTokens)/1000000*modelCost.InputPerMillion +
			float64(log.CompletionTokens)/1000000*modelCost.OutputPerMillion +
			modelCost.RequestCost
	}

	var fixedCostUSD float64
	if username == "" && tokenName == "" && modelName == "" && group == "" {
		fixedCostUSD = calculateFixedCostUSD(costConfig, startTimestamp, endTimestamp, channel)
	}
	upstreamCostUSD := usageCostUSD + fixedCostUSD
	stat.CostConfigured = (stat.Count == 0 || stat.CostUnconfiguredLogs == 0) && (stat.CostConfiguredLogs > 0 || len(costConfig.FixedCosts) > 0)
	stat.UsageCostQuota = int(math.Round(usageCostUSD * common.QuotaPerUnit))
	stat.FixedCostQuota = int(math.Round(fixedCostUSD * common.QuotaPerUnit))
	stat.UpstreamCostQuota = int(math.Round(upstreamCostUSD * common.QuotaPerUnit))
	stat.NetProfitQuota = stat.Quota - stat.UpstreamCostQuota
	if stat.Quota > 0 && stat.CostConfigured {
		stat.ProfitRate = float64(stat.NetProfitQuota) / float64(stat.Quota)
	}
	return nil
}

func SumUsedToken(logType int, startTimestamp int64, endTimestamp int64, modelName string, username string, tokenName string) (token int) {
	tx := LOG_DB.Table("logs").Select("ifnull(sum(prompt_tokens),0) + ifnull(sum(completion_tokens),0)")
	if username != "" {
		tx = tx.Where("username = ?", username)
	}
	if tokenName != "" {
		tx = tx.Where("token_name = ?", tokenName)
	}
	if startTimestamp != 0 {
		tx = tx.Where("created_at >= ?", startTimestamp)
	}
	if endTimestamp != 0 {
		tx = tx.Where("created_at <= ?", endTimestamp)
	}
	if modelName != "" {
		tx = tx.Where("model_name = ?", modelName)
	}
	tx.Where("type = ?", LogTypeConsume).Scan(&token)
	return token
}

func DeleteOldLog(ctx context.Context, targetTimestamp int64, limit int) (int64, error) {
	var total int64 = 0

	for {
		if nil != ctx.Err() {
			return total, ctx.Err()
		}

		result := LOG_DB.Where("created_at < ?", targetTimestamp).Limit(limit).Delete(&Log{})
		if nil != result.Error {
			return total, result.Error
		}

		total += result.RowsAffected

		if result.RowsAffected < int64(limit) {
			break
		}
	}

	return total, nil
}


// UserConsumptionRank is one row of the boss "user contribution board".
type UserConsumptionRank struct {
	Username    string `json:"username" gorm:"column:username"`
	TotalQuota  int64  `json:"total_quota" gorm:"column:total_quota"`
	RecentQuota int64  `json:"recent_quota" gorm:"column:recent_quota"`
	Count       int64  `json:"count" gorm:"column:count"`
}

// GetUserConsumptionRank aggregates consume logs by username.
// recentSince: unix ts for the "recent window" (e.g. 7 days ago); rows ordered by total desc.
func GetUserConsumptionRank(recentSince int64, limit int) (ranks []UserConsumptionRank, err error) {
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	err = LOG_DB.Table("logs").
		Select("username, "+
			"coalesce(sum(quota),0) total_quota, "+
			"coalesce(sum(case when created_at >= ? then quota else 0 end),0) recent_quota, "+
			"count(*) count", recentSince).
		Where("type = ?", LogTypeConsume).
		Where("username <> ''").
		Group("username").
		Order("total_quota desc").
		Limit(limit).
		Scan(&ranks).Error
	return ranks, err
}
