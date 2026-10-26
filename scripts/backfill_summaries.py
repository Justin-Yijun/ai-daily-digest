#!/usr/bin/env python3
"""
回填历史日报里缺失的中文摘要
------------------------------
为什么需要它：LLM 通道挂掉时 collect.py 不会中断，条目会退回显示原文（俄语/日语/
英文，HN 条目甚至整段空白）。2026-10-21 起 NVIDIA 下架了写死的模型，接口 404，
连续 5 天的日报都是这种状态。等通道恢复后，用这个脚本把缺的摘要补上。

用法：
  python scripts/backfill_summaries.py                # 补所有缺摘要的日期
  python scripts/backfill_summaries.py 2026-10-21 2026-10-22
  python scripts/backfill_summaries.py --dry-run      # 只报告，不改文件

补完还要重建页面：
  python scripts/build_weekly.py && python scripts/build_site.py

需要的环境变量与 collect.py 完全一致（NVIDIA_API_KEY / AGNES_API_KEY /
DEEPSEEK_API_KEY，有任意一个即可）。
"""

import json
import sys
from datetime import datetime

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import collect  # noqa: E402  （同目录的 collect.py，复用其 LLM 通道与摘要逻辑）


def digest_paths(dates):
    if dates:
        return [collect.DIGEST_DIR / f"{d}.json" for d in dates]
    return sorted(collect.DIGEST_DIR.glob("*.json"))


def load_state():
    if collect.STATE_PATH.exists():
        return json.loads(collect.STATE_PATH.read_text(encoding="utf-8"))
    return {"items": {}}


def main(argv):
    dry = "--dry-run" in argv
    dates = [a for a in argv if not a.startswith("-")]

    if not collect.llm_providers():
        print("[backfill] 没有任何 LLM 通道的 key，先配好环境变量再跑", file=sys.stderr)
        return 2

    state = load_state()
    now = datetime.now(collect.CST)
    touched = 0

    for path in digest_paths(dates):
        if not path.exists():
            print(f"[backfill] 跳过（不存在）: {path.name}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("items", [])
        missing = [it for it in items if not (it.get("summary_zh") or "").strip()]
        print(f"\n[backfill] {path.name}: {len(items) - len(missing)}/{len(items)} 条已有摘要")
        if not missing:
            continue
        if dry:
            for it in missing:
                print(f"   缺: {it.get('title')}")
            continue

        left = collect.summarize(items, now)
        data["summary_missing"] = left
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        touched += 1
        print(f"[backfill] {path.name} 写入完成，仍缺 {len(left)} 条")

        for it in items:
            rec = state["items"].get(it.get("link"))
            if not rec:
                continue
            if it.get("summary_zh"):
                rec["summary_zh"] = it["summary_zh"]
            if it.get("why_zh"):
                rec["why_zh"] = it["why_zh"]

    if touched and not dry:
        collect.STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"\n[backfill] 已更新 {touched} 份日报 + state/seen.json")
        print("[backfill] 记得重建页面：python scripts/build_weekly.py && python scripts/build_site.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
