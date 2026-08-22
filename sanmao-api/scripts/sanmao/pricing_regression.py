#!/usr/bin/env python3
"""
sanmao 定价回归测试 —— 断言"用户实付 == 上游成本 × 1.3"（利润恒 30%）。

用法:
    python3 pricing_regression.py [BASE_URL]
    默认 BASE_URL = http://localhost:8899  (走 ssh -N -L 8899:127.0.0.1:80 aliyun-120 隧道)

判据（全部来自 memory: sanmao-visioncoder-relay）:
  实付输入价/1M = model_ratio * 2 * group_ratio        应 == 官方输入 * pool_mult * 1.3
  实付输出价/1M = 实付输入 * completion_ratio           应 == 官方输出 * pool_mult * 1.3
  实付缓存读/1M = 实付输入 * cache_ratio                应 == 官方缓存读 * pool_mult * 1.3
  其中 claude 按池统一价（同池所有模型同实付），gpt/grok 按模型 = 官方 * pool_mult。

退出码: 0 全绿, 1 有断言失败。
"""
import sys, json, urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8899"

# --- 上游各池成本倍率 (相对官方零售价) ---
POOL_MULT = {
    "claude-kiro": None,   # claude 走统一价，见 CLAUDE_FLAT
    "claude-max": None,
    "claude-distill": None,
    "gpt-pro": 0.11,
    "gpt-cheap": 0.25,
    "grok": 0.15,
}
# claude 按池统一价（上游实付，$/1M 输入,输出）—— 与具体模型无关
CLAUDE_FLAT = {
    "claude-kiro": {"in": 0.70, "out": 3.50},
    "claude-max": {"in": 12.50, "out": 62.50},
    "claude-distill": {"in": 15.0, "out": 75.0},
}
MARKUP = 1.3

# --- 官方零售价 $/1M (input, output, cacheRead) —— 与前端 officialPrices.js 同源 ---
OFFICIAL = {
    "claude-fable-5": (10, 50, 1), "claude-haiku-4-5-20251001": (1, 5, 0.1),
    "claude-opus-4-5-20251101": (5, 25, 0.5), "claude-opus-4-6": (5, 25, 0.5),
    "claude-opus-4-7": (5, 25, 0.5), "claude-opus-4-8": (5, 25, 0.5),
    "claude-opus-5": (5, 25, 0.5), "claude-sonnet-4-5-20250929": (3, 15, 0.3),
    "claude-sonnet-4-6": (3, 15, 0.3), "claude-sonnet-5": (2, 10, 0.2),
    "codex-auto-review": (0.2, 1.2, 0.02), "gpt-5.2": (1.75, 14, 0.175),
    "gpt-5.3-codex": (1.75, 14, 0.175), "gpt-5.3-codex-spark": (1.75, 14, 0.175),
    "gpt-5.4": (2.5, 15, 0.25), "gpt-5.4-mini": (0.75, 4.5, 0.075),
    "gpt-5.5": (5, 30, 0.5), "gpt-5.6": (5, 30, 0.5), "gpt-5.6-luna": (0.2, 1.2, 0.02),
    "gpt-5.6-sol": (5, 30, 0.5), "gpt-5.6-terra": (2, 12, 0.2),
    "gpt-image-1": (5, None, 1.25), "gpt-image-1.5": (5, 10, 1.25),
    "gpt-image-2": (5, 10, 1.25), "grok-4.6": (2, 6, 0.5),
}

TOL = 0.02  # 相对误差容忍 2%


def approx(a, b):
    if b == 0:
        return abs(a) < 1e-6
    return abs(a - b) / abs(b) <= TOL


def expected_paid(model, group, kind):
    """kind in {in,out,cache}; 返回期望实付 $/1M。claude 用池统一价，其它按模型。"""
    off = OFFICIAL[model]
    if group in CLAUDE_FLAT:
        flat = CLAUDE_FLAT[group]
        if kind == "in":
            return flat["in"] * MARKUP
        if kind == "out":
            return flat["out"] * MARKUP
        if kind == "cache":
            # 缓存读上游≈输入×0.1
            return flat["in"] * 0.1 * MARKUP
    else:
        mult = POOL_MULT[group]
        idx = {"in": 0, "out": 1, "cache": 2}[kind]
        base = off[idx]
        if base is None:
            return None
        return base * mult * MARKUP
    return None


def main():
    data = json.load(urllib.request.urlopen(BASE + "/api/pricing", timeout=15))
    gr = data["group_ratio"]
    models = {m["model_name"]: m for m in data["data"]}

    fails, checks = [], 0

    # 1) 覆盖性: 每个在售模型都要有官方价 + 四张 ratio 齐
    for name, m in models.items():
        if name not in OFFICIAL:
            fails.append(f"[COVERAGE] {name}: 官方价表缺失")
        for f in ("model_ratio", "completion_ratio"):
            if m.get(f) in (None, ""):
                fails.append(f"[RATIO] {name}: 缺 {f}")
        if m.get("cache_ratio") in (None, ""):
            fails.append(f"[CACHE] {name}: 缺 cache_ratio（会按全价狂扣缓存！）")

    # 2) 实付 == 成本×1.3，逐模型逐池逐口径
    for name, m in models.items():
        if name not in OFFICIAL:
            continue
        mr = m["model_ratio"]
        cr = m["completion_ratio"]
        cacher = m.get("cache_ratio")
        for group in m.get("enable_groups", []):
            if group not in gr:
                continue
            g = gr[group]
            paid_in = mr * 2 * g
            paid_out = paid_in * cr
            paid_cache = paid_in * cacher if cacher else None

            for kind, paid in (("in", paid_in), ("out", paid_out), ("cache", paid_cache)):
                exp = expected_paid(name, group, kind)
                if exp is None or paid is None:
                    continue
                checks += 1
                if not approx(paid, exp):
                    fails.append(
                        f"[PRICE] {name} @ {group} {kind}: 实付 ${paid:.4f} != 期望 ${exp:.4f} "
                        f"(成本×1.3)  [MR={mr} CR={cr} cache={cacher} GR={g}]"
                    )

    print(f"检查项: {checks}  |  覆盖模型: {len(models)}  |  失败: {len(fails)}")
    if fails:
        print("\n".join("  FAIL " + f for f in fails))
        print(f"\n❌ 回归失败：{len(fails)} 条")
        return 1
    print("✅ 全绿：所有在售模型 × 所有池 × (输入/输出/缓存) 实付 == 上游成本 × 1.3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
