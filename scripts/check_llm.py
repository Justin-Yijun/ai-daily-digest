#!/usr/bin/env python3
"""
LLM 通道自检
------------
用一条真实条目逐个通道发一次请求，报告：HTTP 状态、耗时、返回的 JSON 是否合法、
以及能否按 id 对齐。不写任何文件，可以随便跑。

为什么需要它：摘要链路是静默降级的，某个通道挂了页面不会报错，只会悄悄退回显示
原文。2026-10-21 那次就是 NVIDIA 下架模型、5 天没人发现。上线前 / 换 key 后 /
怀疑某条通道时，先跑这个。

用法：
  python scripts/check_llm.py                       # 用最近一期日报的第 0 条
  python scripts/check_llm.py --item 3              # 指定第 3 条
  python scripts/check_llm.py --model gemini-3.1-flash-lite   # 覆盖某通道模型

环境变量与 collect.py 一致（NVIDIA_API_KEY / AGNES_API_KEY / GEMINI_API_KEY /
DEEPSEEK_API_KEY），有多少测多少。本机走代理时加 HTTPS_PROXY。
"""

import json
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import collect  # noqa: E402


def latest_items():
    files = sorted(collect.DIGEST_DIR.glob("*.json"))
    if not files:
        print("[check] 没有 digest/*.json，无法取样本条目", file=sys.stderr)
        sys.exit(2)
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    return files[-1].name, data.get("items", [])


def probe(p, prompt):
    """返回 (ok, 说明)。直接发请求以便拿到状态码和错误体。"""
    body = {
        "model": p["model"],
        "messages": [
            {"role": "system", "content": collect.SUMMARY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        p["base"] + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + p["key"],
            "User-Agent": "pi-check-llm",
        },
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200].replace("\n", " ")
        return False, f"HTTP {e.code} {detail}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    dt = time.time() - t0
    try:
        content = json.loads(raw)["choices"][0]["message"].get("content")
    except Exception as e:  # noqa: BLE001
        return False, f"{dt:.1f}s 响应结构异常 {type(e).__name__}: {e}"
    if not content:
        return False, f"{dt:.1f}s content 为空（推理可能吃满 token）"
    try:
        arr = json.loads(content).get("items") or []
    except Exception as e:  # noqa: BLE001
        return False, f"{dt:.1f}s 返回非合法 JSON: {e}"
    ids = [x.get("id") for x in arr]
    if 0 not in ids:
        return False, f"{dt:.1f}s JSON 合法但缺少 id=0（拿到 {ids}）"
    sample = (arr[0].get("summary") or "")[:60]
    return True, f"{dt:.1f}s id={ids} 摘要「{sample}」"


def main(argv):
    idx = 0
    for i, a in enumerate(argv):
        if a == "--item" and i + 1 < len(argv):
            idx = int(argv[i + 1])
    override = ""
    for i, a in enumerate(argv):
        if a == "--model" and i + 1 < len(argv):
            override = argv[i + 1]

    providers = collect.llm_providers()
    if not providers:
        print("[check] 一个通道都没配（没有任何 *_API_KEY）", file=sys.stderr)
        return 2
    name, items = latest_items()
    if not items:
        print(f"[check] {name} 里没有条目", file=sys.stderr)
        return 2
    item = items[min(idx, len(items) - 1)]
    print(f"[check] 样本：{name} 第 {idx} 条「{item['title'][:50]}」")
    print(f"[check] 待测通道：{', '.join(p['name'] for p in providers)}\n")

    prompt = collect.build_prompt([item])
    bad = 0
    for p in providers:
        if override:
            p = dict(p, model=override)
        ok, note = probe(p, prompt)
        mark = "✓" if ok else "✗"
        print(f"  {mark} {p['name']:9s} {p['model']:32s} {note}")
        if not ok:
            bad += 1
    print()
    if bad == len(providers):
        print(f"[check] 全部 {bad} 个通道不可用")
        return 1
    print(f"[check] {len(providers) - bad}/{len(providers)} 个通道可用")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
