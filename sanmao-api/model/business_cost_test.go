package model

import "testing"

func TestHasBusinessCostForChannelModelAllowsPerRequestCost(t *testing.T) {
	config := BusinessCostConfig{
		Channels: map[string]BusinessCostChannelConfig{
			"1": {
				Models: map[string]BusinessCostModelConfig{
					"gpt-5.4": {RequestCost: 0.0035225},
				},
			},
		},
	}

	if !HasBusinessCostForChannelModel(config, 1, "gpt-5.4") {
		t.Fatal("expected per-request VisionCoder cost to allow model listing")
	}
	if HasBusinessCostForChannelModel(config, 1, "unknown-model") {
		t.Fatal("expected model without cost to be hidden")
	}
}

func TestHasBusinessCostForChannelModelAllowsBoundFixedCost(t *testing.T) {
	config := BusinessCostConfig{
		FixedCosts: []BusinessFixedCostConfig{
			{Amount: 198, Currency: "CNY", Period: "month", ChannelIDs: []int{5}},
		},
	}

	if !HasBusinessCostForChannelModel(config, 5, "qwen3.7-plus") {
		t.Fatal("expected channel-bound Aliyun Token Plan cost to allow model listing")
	}
	if HasBusinessCostForChannelModel(config, 2, "claude-sonnet-4-6") {
		t.Fatal("expected unbound channel to be hidden")
	}
}

func TestHasBusinessCostForChannelModelDoesNotUseGlobalFixedCostForListing(t *testing.T) {
	config := BusinessCostConfig{
		FixedCosts: []BusinessFixedCostConfig{
			{Amount: 20, Currency: "USD", Period: "month"},
		},
	}

	if HasBusinessCostForChannelModel(config, 3, "claude-opus-4-6") {
		t.Fatal("global fixed costs should not make every model listable")
	}
}

func TestBusinessFixedCostPeriodSecondsSupportsHourlyGpuCost(t *testing.T) {
	if got := businessFixedCostPeriodSeconds("hour"); got != 60*60 {
		t.Fatalf("expected hourly fixed cost period to be 3600 seconds, got %v", got)
	}
}
