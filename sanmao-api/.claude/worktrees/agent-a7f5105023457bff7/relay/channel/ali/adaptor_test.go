package ali

import (
	"testing"

	relaycommon "github.com/QuantumNous/new-api/relay/common"
	"github.com/QuantumNous/new-api/types"
)

func TestSupportsAliAnthropicMessagesAllowlist(t *testing.T) {
	tests := []struct {
		model string
		want  bool
	}{
		{model: "qwen3.7-plus", want: true},
		{model: "qwen3.7-max", want: true},
		{model: "qwen3.7-max-2026-06-08", want: true},
		{model: "deepseek-v4-pro", want: false},
		{model: "qwen-image", want: false},
	}

	for _, tt := range tests {
		if got := supportsAliAnthropicMessages(tt.model); got != tt.want {
			t.Fatalf("supportsAliAnthropicMessages(%q) = %v, want %v", tt.model, got, tt.want)
		}
	}
}

func TestGetRequestURLForClaudeFormatUsesExpectedAliEndpoint(t *testing.T) {
	adaptor := &Adaptor{}
	baseURL := "https://dashscope.aliyuncs.com"

	qwenInfo := &relaycommon.RelayInfo{
		RelayFormat: types.RelayFormatClaude,
		ChannelMeta: &relaycommon.ChannelMeta{
			ChannelBaseUrl:    baseURL,
			UpstreamModelName: "qwen3.7-max",
		},
	}
	qwenURL, err := adaptor.GetRequestURL(qwenInfo)
	if err != nil {
		t.Fatalf("unexpected error for qwen model: %v", err)
	}
	if want := baseURL + "/apps/anthropic/v1/messages"; qwenURL != want {
		t.Fatalf("qwen URL = %q, want %q", qwenURL, want)
	}

	deepseekInfo := &relaycommon.RelayInfo{
		RelayFormat: types.RelayFormatClaude,
		ChannelMeta: &relaycommon.ChannelMeta{
			ChannelBaseUrl:    baseURL,
			UpstreamModelName: "deepseek-v4-pro",
		},
	}
	deepseekURL, err := adaptor.GetRequestURL(deepseekInfo)
	if err != nil {
		t.Fatalf("unexpected error for deepseek model: %v", err)
	}
	if want := baseURL + "/compatible-mode/v1/chat/completions"; deepseekURL != want {
		t.Fatalf("deepseek URL = %q, want %q", deepseekURL, want)
	}
}
