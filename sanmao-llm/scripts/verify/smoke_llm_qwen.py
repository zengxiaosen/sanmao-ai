from __future__ import annotations

import json
import re

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


# 这个脚本只做一件事：验证旧 extractor 链路里的本地 Qwen 模型是否能加载，并输出可解析 JSON。
# 它不参与训练，不写入主特征文件，也不做回测。
#
# 注意：
#   - 这个脚本保留给旧 qwen3-8b-awq / llm-env 兼容链路。
#   - 仓库主线已经切到 Qwen3-Coder，不再推荐把这个 8B 当作默认模型。
#   - 新的 coding-agent 主线请改用：
#       scripts/verify/check_qwen3_coder_vllm.sh
#       scripts/verify/smoke_qwen3_coder_agent.sh
#
# 默认模型路径可以用环境变量覆盖：
#   MODEL_PATH=/path/to/model python scripts/verify/smoke_llm_qwen.py
MODEL_PATH = "/root/autodl-tmp/models/qwen3-8b-awq"


prompt = """/no_think
You are a financial information extraction engine.
Return exactly one compact JSON object and nothing else. Do not explain. Do not use markdown.

Schema:
{"event_type":"earnings|macro|product|management|legal|supply_chain|other","sentiment":number_between_-1_and_1,"confidence":number_between_0_and_1,"impact_horizon":"intraday|1-5d|1-20d|long_term","risk_tags":["string"]}

Rules:
- confidence means extraction reliability, not stock-up probability.
- event_type must be one of the schema choices.
- impact_horizon must be one of the schema choices.

Symbol: AAPL
Title: Apple beat earnings expectations but warned gross margin may be pressured next quarter.
Text: Apple reported stronger revenue than analysts expected, but management said component costs may pressure margins in the next quarter.

JSON:"""


print("cuda", torch.cuda.is_available())
print("model_path", MODEL_PATH)

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    device_map="auto",
    trust_remote_code=True,
)

messages = [{"role": "user", "content": prompt}]
try:
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
except TypeError:
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

inputs = tokenizer(text, return_tensors="pt").to(model.device)
with torch.inference_mode():
    output_ids = model.generate(
        **inputs,
        max_new_tokens=96,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        pad_token_id=tokenizer.eos_token_id,
    )

generated = tokenizer.decode(output_ids[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True).strip()
print("generated:", generated)

match = re.search(r"\{.*\}", generated, flags=re.S)
if not match:
    raise SystemExit("no json object in generated output")

payload = json.loads(match.group(0))
print("parsed:", json.dumps(payload, ensure_ascii=False, sort_keys=True))
