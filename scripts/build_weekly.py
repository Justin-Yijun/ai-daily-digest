#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 前沿日报 · 周报生成器
-------------------------
把 digest/*.json 里同一 ISO 周（周一~周日）的条目汇总、按链接去重、
按「面试技能树」加权排序，取前 N 条生成「本周精选」，并按技能树分支归类：

  weekly/YYYY-Www.md     周报正文（Markdown，归档用）
  weekly/YYYY-Www.json   周报结构化数据（站点生成用，含 groups）

生成时机：周日（CST）生成本周；同时补上周（若缺失）。
条目已带每日生成好的中文摘要，所以周报不再调用大模型，零额外成本。
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGEST_DIR = ROOT / "digest"
WEEKLY_DIR = ROOT / "weekly"
CST = timezone(timedelta(hours=8))

# 复用采集器里的技能树匹配，保证日报打分和周报归类用的是同一套规则
sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import learn_score_item, parse_dt  # noqa: E402

SRC_NAME = {
    "github": "GitHub",
    "youtube": "YouTube",
    "blog": "博客",
    "paper": "论文",
    "hackernews": "Hacker News",
}
SRC_ICON = {
    "github": "🐙",
    "youtube": "📺",
    "blog": "📝",
    "paper": "📄",
    "hackernews": "💬",
}


def log(*a):
    print(*a, flush=True)


def week_key(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_days(anchor):
    """返回 anchor 所在 ISO 周的周一~周日 7 个日期字符串。"""
    mon = anchor - timedelta(days=anchor.isoweekday() - 1)
    return [(mon + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def load_digests():
    out = {}
    for p in DIGEST_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out[d.get("date")] = d
        except Exception as e:  # noqa: BLE001
            log(f"  [warn] 读取失败 {p.name}: {e}")
    return out


def backfill_learn_scores(all_d, scoring, now):
    """给历史 digest（没有 learn_score 字段）补算面试学习价值，保证旧数据也按新规则排序。"""
    for d in all_d.values():
        for it in d.get("items") or []:
            if it.get("learn_score") is not None:
                continue
            probe = dict(it)
            dt = it.get("dt")
            probe["dt"] = parse_dt(dt) if isinstance(dt, str) else dt
            it["learn_score"] = learn_score_item(probe, scoring, now)
            it["skills"] = probe.get("skills") or it.get("skills") or []


def weekly_score(it, skill_penalty):
    """周报排序分：用「面试学习价值」而不是热度分，未归入技能树的再降权。"""
    s = float(
        it.get("learn_score") if it.get("learn_score") is not None else it.get("score", 0)
    )
    if not it.get("skills"):
        s *= skill_penalty
    return s


def pick_week(all_d, days, top_n, skill_penalty=0.7):
    """汇总这一周的条目：按链接去重（保留最高周报分），
    按「面试学习价值」排序取前 N。"""
    best = {}
    for date_s in days:
        d = all_d.get(date_s)
        if not d:
            continue
        for it in d.get("items") or []:
            u = it.get("link")
            if not u:
                continue
            if u not in best or weekly_score(it, skill_penalty) > weekly_score(best[u], skill_penalty):
                best[u] = it
    # 同一篇内容（如博客与视频同标题）只留最高分的一条
    out, seen_titles = [], set()
    for it in sorted(best.values(), key=lambda x: weekly_score(x, skill_penalty), reverse=True):
        t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (it.get("title") or "").lower())
        if t and t in seen_titles:
            continue
        if t:
            seen_titles.add(t)
        out.append(it)
        if len(out) >= top_n:
            break
    return out


def group_by_skill(top, order):
    """按技能树分支归类；多分支条目只归到配置里最靠前的那一个。"""
    grouped = {k: [] for k in order}
    other = []
    for it in top:
        skills = it.get("skills") or []
        primary = next((s for s in skills if s in grouped), None)
        (grouped[primary] if primary else other).append(it)
    return grouped, other


def fmt_item(it, idx=None):
    ex = it.get("extra") or {}
    src = it.get("source")
    badge = ""
    if src == "github":
        badge = f"⭐ {ex.get('stars', 0)}"
        if ex.get("language"):
            badge += f" · {ex['language']}"
        if ex.get("created"):
            badge += f" · 新建 {ex['created']}"
    elif src == "hackernews":
        badge = f"🔥 HN {ex.get('points', 0)} 分 · 💬 {ex.get('comments', 0)}"
    elif src == "paper":
        badge = f"📄 HF 👍 {ex['upvotes']}" if ex.get("upvotes") else "📄 论文"
    elif src == "youtube":
        badge = "🎬 视频"
    else:
        badge = "📝 文章"
    dt = it.get("dt")
    date_s = str(dt)[5:10] if dt else ""
    head = (
        f"### {idx}. [{it.get('title')}]({it.get('link')})"
        if idx
        else f"- **[{it.get('title')}]({it.get('link')})**"
    )
    lines = [head, f"  `{it.get('source_label')}` · {badge} · {date_s}"]
    if it.get("summary_zh"):
        lines.append(f"  **摘要**：{it['summary_zh']}")
    if it.get("why_zh"):
        lines.append(f"  **为什么值得看**：{it['why_zh']}")
    elif it.get("summary"):
        lines.append(f"  {it['summary'][:200]}")
    return "\n".join(lines)


def render_md(key, days, top, now, order, labels):
    fresh = [i for i in top if i.get("flag") == "new"]
    n_dup = len(top) - len(fresh)
    out = [
        f"# AI 前沿周报 · {key}",
        "",
        f"> 覆盖 {days[0]} ~ {days[-1]}　|　本周精选 {len(top)} 条"
        + (f"（其中 {n_dup} 条此前推荐过）" if n_dup else ""),
        ">",
        f"> 生成时间：{now.astimezone(CST).strftime('%Y-%m-%d %H:%M')} (CST)",
        ">",
        "> 按 Agent / AI 面试技能树归类，优先收录可复习、能讲出来的实践内容",
        "",
        "---",
        "",
    ]
    grouped, other = group_by_skill(top, order)
    for k in order:
        group = grouped[k]
        if not group:
            continue
        out.append(f"## 🧠 {labels.get(k, k)}（{len(group)}）")
        out.append("")
        for it in group:
            out.append(fmt_item(it))
            out.append("")
    if other:
        out.append(f"## 📰 其他动态（{len(other)}）")
        out.append("")
        for it in other:
            out.append(fmt_item(it))
            out.append("")

    out.append("---")
    out.append("")
    out.append("*由 GitHub Actions 自动汇总生成*")
    return "\n".join(out).rstrip() + "\n"


def main():
    now = datetime.now(timezone.utc)
    today = now.astimezone(CST)
    all_d = load_digests()
    if not all_d:
        log("[weekly] 没有 digest/*.json，先跑 collect.py")
        return

    cfg_path = ROOT / "config" / "sources.json"
    top_n = 12
    tree, order, labels, skill_penalty, scoring = {}, [], {}, 0.7, {}
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        top_n = int(cfg.get("output", {}).get("weekly_top", 12))
        scoring = cfg.get("scoring") or {}
        tree = scoring.get("interview_skill_tree") or {}
        order = [k for k in tree if not k.startswith("_")]
        labels = scoring.get("interview_skill_labels") or {}
        skill_penalty = float(cfg.get("output", {}).get("weekly_skill_penalty", 0.7))
    except Exception:  # noqa: BLE001
        pass
    backfill_learn_scores(all_d, scoring, now)

    # 周日生成本周；任何时候都补一份「上周」（若缺失）
    # 也可用 WEEK_ANCHOR=YYYY-MM-DD 手动补任意一周
    targets = []
    anchor_env = os.environ.get("WEEK_ANCHOR")
    if anchor_env:
        a = None
        try:
            a = datetime.strptime(anchor_env, "%Y-%m-%d").replace(tzinfo=CST)
        except ValueError:
            log(f"[weekly] WEEK_ANCHOR 格式应为 YYYY-MM-DD，收到 {anchor_env!r}")
        if a:
            targets.append(a)
    else:
        if today.isoweekday() == 7:
            targets.append(today)
        targets.append(today - timedelta(days=7))

    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    for anchor in targets:
        key = week_key(anchor)
        days = week_days(anchor)
        is_current = (not anchor_env) and anchor.isoweekday() == 7
        md_path = WEEKLY_DIR / f"{key}.md"
        if md_path.exists() and not is_current:
            continue  # 往周已有就不重写
        top = pick_week(all_d, days, top_n, skill_penalty)
        if not top:
            log(f"[weekly] {key}（{days[0]}~{days[-1]}）没有内容，跳过")
            continue
        md = render_md(key, days, top, now, order, labels)
        md_path.write_text(md, encoding="utf-8")
        grouped, other = group_by_skill(top, order)
        groups = [
            {"skill": k, "label": labels.get(k, k), "items": grouped[k]}
            for k in order
            if grouped[k]
        ]
        if other:
            groups.append({"skill": "", "label": "其他动态", "items": other})
        data = {
            "week": key,
            "start": days[0],
            "end": days[-1],
            "generated": now.astimezone(CST).strftime("%Y-%m-%d %H:%M"),
            "groups": groups,
            "items": top,
        }
        (WEEKLY_DIR / f"{key}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        log(f"[weekly] 已写出 {key}（{days[0]}~{days[-1]}，{len(top)} 条）")


if __name__ == "__main__":
    main()
