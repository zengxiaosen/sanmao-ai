package codex

import (
	"errors"
	"strings"

	"github.com/QuantumNous/new-api/common"
)

type CredentialMode string

const (
	CredentialModeOAuth  CredentialMode = "oauth_json"
	CredentialModeAPIKey CredentialMode = "api_key"
)

type OAuthKey struct {
	IDToken      string `json:"id_token,omitempty"`
	AccessToken  string `json:"access_token,omitempty"`
	RefreshToken string `json:"refresh_token,omitempty"`

	AccountID   string `json:"account_id,omitempty"`
	LastRefresh string `json:"last_refresh,omitempty"`
	Email       string `json:"email,omitempty"`
	Type        string `json:"type,omitempty"`
	Expired     string `json:"expired,omitempty"`
}

type Credential struct {
	Mode     CredentialMode
	APIKey   string
	OAuthKey *OAuthKey
}

func ParseOAuthKey(raw string) (*OAuthKey, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, errors.New("codex channel: empty oauth key")
	}
	var key OAuthKey
	if err := common.Unmarshal([]byte(raw), &key); err != nil {
		return nil, errors.New("codex channel: invalid oauth key json")
	}
	return &key, nil
}

func DetectCredentialMode(raw string) (CredentialMode, error) {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return "", errors.New("codex channel: empty credential")
	}
	if strings.HasPrefix(trimmed, "{") {
		return CredentialModeOAuth, nil
	}
	if strings.HasPrefix(trimmed, "sk-") {
		return CredentialModeAPIKey, nil
	}
	return "", errors.New("codex channel: credential must be OAuth JSON or an sk- API key")
}

func ParseCredential(raw string) (*Credential, error) {
	trimmed := strings.TrimSpace(raw)
	mode, err := DetectCredentialMode(trimmed)
	if err != nil {
		return nil, err
	}
	credential := &Credential{Mode: mode}
	if mode == CredentialModeAPIKey {
		credential.APIKey = trimmed
		return credential, nil
	}
	oauthKey, err := ParseOAuthKey(trimmed)
	if err != nil {
		return nil, err
	}
	credential.OAuthKey = oauthKey
	return credential, nil
}
