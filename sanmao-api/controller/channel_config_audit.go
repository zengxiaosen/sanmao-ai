package controller

import (
	"net/http"
	"strconv"
	"strings"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/model"
	"github.com/QuantumNous/new-api/setting/ratio_setting"
	"github.com/gin-gonic/gin"
)

type channelConfigAuditIssue struct {
	ChannelID int    `json:"channel_id"`
	Channel   string `json:"channel"`
	Group     string `json:"group"`
	Model     string `json:"model"`
	Problem   string `json:"problem"`
	Detail    string `json:"detail"`
}

type channelConfigAuditSummary struct {
	Channels               int `json:"channels"`
	EnabledChannels        int `json:"enabled_channels"`
	ModelsChecked          int `json:"models_checked"`
	MissingAbilities       int `json:"missing_abilities"`
	MissingPriceOrRatio    int `json:"missing_price_or_ratio"`
	MissingCompletionRatio int `json:"missing_completion_ratio"`
	FallbackOnlyRatio      int `json:"fallback_only_ratio"`
	FallbackOnlyCompletion int `json:"fallback_only_completion"`
}

func AuditChannelConfig(c *gin.Context) {
	channels, err := model.GetAllChannels(0, 0, true, false)
	if err != nil {
		common.ApiError(c, err)
		return
	}

	enabledAbilities := model.GetAllEnableAbilities()
	abilitySet := make(map[string]struct{}, len(enabledAbilities))
	for _, ability := range enabledAbilities {
		key := buildChannelAbilityAuditKey(ability.ChannelId, ability.Group, ability.Model)
		abilitySet[key] = struct{}{}
	}

	issues := make([]channelConfigAuditIssue, 0)
	summary := channelConfigAuditSummary{
		Channels: len(channels),
	}

	for _, channel := range channels {
		if channel == nil {
			continue
		}
		if channel.Status == common.ChannelStatusEnabled {
			summary.EnabledChannels++
		}

		models := splitAuditValues(channel.Models)
		groups := splitAuditValues(channel.Group)
		if len(groups) == 0 {
			groups = []string{"default"}
		}

		for _, modelName := range models {
			summary.ModelsChecked++

			modelPrice, hasPrice := ratio_setting.GetModelPrice(modelName, false)
			modelRatio, hasRatio, matchedRatioName := ratio_setting.GetModelRatio(modelName)
			_ = modelPrice
			_ = modelRatio

			if !hasPrice && !hasRatio {
				summary.MissingPriceOrRatio++
				issues = append(issues, channelConfigAuditIssue{
					ChannelID: channel.Id,
					Channel:   channel.Name,
					Group:     channel.Group,
					Model:     modelName,
					Problem:   "missing_price_or_ratio",
					Detail:    "model has neither configured price nor resolved ratio",
				})
			} else if hasRatio && matchedRatioName != ratio_setting.FormatMatchingModelName(modelName) && !ratio_setting.ContainsExactModelRatio(modelName) {
				summary.FallbackOnlyRatio++
				issues = append(issues, channelConfigAuditIssue{
					ChannelID: channel.Id,
					Channel:   channel.Name,
					Group:     channel.Group,
					Model:     modelName,
					Problem:   "fallback_only_ratio",
					Detail:    "model ratio resolves only via family fallback: " + matchedRatioName,
				})
			}

			completionInfo := ratio_setting.GetCompletionRatioInfo(modelName)
			exactCompletion := ratio_setting.ContainsExactCompletionRatio(modelName)
			_, hardcodedLocked := getCompletionRatioLockState(modelName)
			if completionInfo.Ratio <= 0 && !exactCompletion && !hardcodedLocked {
				summary.MissingCompletionRatio++
				issues = append(issues, channelConfigAuditIssue{
					ChannelID: channel.Id,
					Channel:   channel.Name,
					Group:     channel.Group,
					Model:     modelName,
					Problem:   "missing_completion_ratio",
					Detail:    "completion ratio is not explicitly configured and has no locked family default",
				})
			} else if !exactCompletion && !hardcodedLocked {
				summary.FallbackOnlyCompletion++
				issues = append(issues, channelConfigAuditIssue{
					ChannelID: channel.Id,
					Channel:   channel.Name,
					Group:     channel.Group,
					Model:     modelName,
					Problem:   "fallback_only_completion",
					Detail:    "completion ratio depends on implicit fallback/default behavior",
				})
			}

			if channel.Status != common.ChannelStatusEnabled {
				continue
			}
			for _, groupName := range groups {
				key := buildChannelAbilityAuditKey(channel.Id, groupName, modelName)
				if _, ok := abilitySet[key]; ok {
					continue
				}
				summary.MissingAbilities++
				issues = append(issues, channelConfigAuditIssue{
					ChannelID: channel.Id,
					Channel:   channel.Name,
					Group:     groupName,
					Model:     modelName,
					Problem:   "missing_ability",
					Detail:    "enabled channel model/group pair is missing from abilities table",
				})
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "",
		"data": gin.H{
			"summary": summary,
			"issues":  issues,
		},
	})
}

func buildChannelAbilityAuditKey(channelID int, groupName string, modelName string) string {
	return strings.Join([]string{strconv.Itoa(channelID), groupName, modelName}, "|")
}

func splitAuditValues(raw string) []string {
	parts := strings.Split(raw, ",")
	values := make([]string, 0, len(parts))
	seen := make(map[string]struct{}, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		if _, ok := seen[part]; ok {
			continue
		}
		seen[part] = struct{}{}
		values = append(values, part)
	}
	return values
}

func getCompletionRatioLockState(modelName string) (float64, bool) {
	info := ratio_setting.GetCompletionRatioInfo(modelName)
	return info.Ratio, info.Locked
}
