package ratio_setting

import "testing"

// 回归护栏（硬编码层）：gpt-5.x 系的 completion ratio 由 getHardcodedCompletionModelRatio
// 强制返回（locked=true，压过 DB），必须 == 官方输出价/输入价。
// 曾经 gpt-5.5/gpt-5.6 系被硬编码成 8（codex 系的值），导致输出 token 多扣 33%。
// claude/grok/codex-auto-review 等靠 DB options 配置，由 python 端到端回归（pricing_regression.py）守护。
// 见 memory: sanmao-visioncoder-relay「实付 == 成本×1.3」。
func TestSanmaoHardcodedCompletionRatios(t *testing.T) {
	InitRatioSettings()

	// model -> 期望 completion ratio (= 官方输出 / 官方输入)
	want := map[string]float64{
		// gpt-5.6 家族：官方 30/5 = 6（terra 12/2=6，luna 1.2/0.2=6）
		"gpt-5.6":       6,
		"gpt-5.6-sol":   6,
		"gpt-5.6-terra": 6,
		"gpt-5.6-luna":  6,
		"gpt-5.5":       6,
		// gpt-5.4 家族：官方 15/2.5 = 6
		"gpt-5.4":      6,
		"gpt-5.4-mini": 6,
		// codex 系：官方 14/1.75 = 8
		"gpt-5.2":             8,
		"gpt-5.3-codex":       8,
		"gpt-5.3-codex-spark": 8,
	}

	for model, exp := range want {
		got := GetCompletionRatio(model)
		if got != exp {
			t.Errorf("completion ratio %s = %v, want %v (官方输出/输入)", model, got, exp)
		}
	}
}
