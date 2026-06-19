package openai

import (
	"testing"

	"github.com/QuantumNous/new-api/constant"
	"github.com/QuantumNous/new-api/dto"
	relaycommon "github.com/QuantumNous/new-api/relay/common"
	relayconstant "github.com/QuantumNous/new-api/relay/constant"
	"github.com/QuantumNous/new-api/types"
)

func TestGetRequestURLAzureResponsesByIDUsesResponsePath(t *testing.T) {
	adaptor := &Adaptor{}
	info := &relaycommon.RelayInfo{
		RelayMode:      relayconstant.RelayModeResponses,
		RelayFormat:    types.RelayFormatOpenAIResponses,
		RequestURLPath: "/v1/responses/resp_123",
		ChannelMeta: &relaycommon.ChannelMeta{
			ChannelType:          constant.ChannelTypeAzure,
			ChannelBaseUrl:       "https://example-resource.openai.azure.com",
			ApiVersion:           "2025-04-01-preview",
			ChannelOtherSettings: dto.ChannelOtherSettings{},
		},
	}

	got, err := adaptor.GetRequestURL(info)
	if err != nil {
		t.Fatalf("GetRequestURL returned error: %v", err)
	}

	want := "https://example-resource.openai.azure.com/openai/v1/responses/resp_123?api-version=preview"
	if got != want {
		t.Fatalf("unexpected request url: got %q want %q", got, want)
	}
}

func TestGetRequestURLAzureCognitiveResponsesByIDUsesConfiguredVersion(t *testing.T) {
	adaptor := &Adaptor{}
	info := &relaycommon.RelayInfo{
		RelayMode:      relayconstant.RelayModeResponses,
		RelayFormat:    types.RelayFormatOpenAIResponses,
		RequestURLPath: "/v1/responses/resp_456",
		ChannelMeta: &relaycommon.ChannelMeta{
			ChannelType:    constant.ChannelTypeAzure,
			ChannelBaseUrl: "https://example.cognitiveservices.azure.com",
			ApiVersion:     "2024-10-21",
			ChannelOtherSettings: dto.ChannelOtherSettings{
				AzureResponsesVersion: "2025-04-01-preview",
			},
		},
	}

	got, err := adaptor.GetRequestURL(info)
	if err != nil {
		t.Fatalf("GetRequestURL returned error: %v", err)
	}

	want := "https://example.cognitiveservices.azure.com/openai/responses/resp_456?api-version=2025-04-01-preview"
	if got != want {
		t.Fatalf("unexpected request url: got %q want %q", got, want)
	}
}
