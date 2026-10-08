#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 前沿日报 · 静态站生成器
---------------------------
读取 digest/*.json，生成可直接托管的静态网站到 site/：

  site/index.html            最新一期
  site/d/YYYY-MM-DD.html     每期独立页面（永久链接）
  site/archive.html          历史归档（按月份组）
  site/about.html            关于
  site/feed.xml              RSS 订阅
  site/style.css             样式

仅使用 Python 标准库。由 Cloudflare Pages 直接托管 site/ 目录。
"""

import html
import json
import os
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGEST_DIR = ROOT / "digest"
WEEKLY_DIR = ROOT / "weekly"
SITE_DIR = ROOT / "site"

CST = timezone(timedelta(hours=8))
SITE_TITLE = "AI 前沿日报"
SITE_DESC = (
    "每天自动采集 GitHub / YouTube / 博客 / 论文 / Hacker News 上"
    "关于 AI、LLM、Agent、Harness 的前沿动态，生成中文摘要。"
)
# 正式对外地址（Cloudflare Pages 自定义域名）。换域名只改这一处，或设环境变量 SITE_URL
SITE_URL = os.environ.get("SITE_URL", "https://aivulcan.de5.net").rstrip("/")

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

STYLE = """\
:root{
  --bg:#070a12;--fg:#e6edf7;--muted:#8b9ab3;
  --card:linear-gradient(180deg,rgba(20,28,46,.86),rgba(14,20,34,.86));
  --card-line:rgba(125,165,225,.16);--line:rgba(125,165,225,.14);--line-strong:rgba(56,189,248,.45);
  --link:#7dd3fc;--link-hover:#a5f3fc;
  --cyan:#22d3ee;--violet:#a78bfa;--tag:rgba(125,165,225,.10);
  --shadow:0 10px 34px rgba(0,0,0,.42);
}
@media (prefers-color-scheme:light){
  :root{
    --bg:#f4f7fc;--fg:#0f172a;--muted:#5c6b85;
    --card:linear-gradient(180deg,#ffffff,#fbfdff);
    --card-line:rgba(30,64,140,.14);--line:rgba(30,64,140,.12);--line-strong:rgba(14,116,200,.4);
    --link:#0369a1;--link-hover:#075985;
    --cyan:#0891b2;--violet:#6d28d9;--tag:rgba(30,64,140,.07);
    --shadow:0 8px 26px rgba(15,23,42,.08);
  }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;color:var(--fg);font:16px/1.72 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;
  background:
    radial-gradient(1100px 560px at 12% -8%,rgba(34,211,238,.10),transparent 62%),
    radial-gradient(900px 480px at 92% -4%,rgba(167,139,250,.10),transparent 58%),
    var(--bg);
  background-attachment:fixed;
}
body::before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:
    linear-gradient(rgba(125,180,255,.05) 1px,transparent 1px),
    linear-gradient(90deg,rgba(125,180,255,.05) 1px,transparent 1px);
  background-size:46px 46px;
  -webkit-mask-image:radial-gradient(ellipse 120% 70% at 50% 0%,#000 18%,transparent 78%);
  mask-image:radial-gradient(ellipse 120% 70% at 50% 0%,#000 18%,transparent 78%);
}
.wrap{position:relative;z-index:1;max-width:840px;margin:0 auto;padding:34px 18px 80px}
header.site{padding:6px 0 20px;margin-bottom:28px;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:14px}
.logo{
  position:relative;flex:none;width:40px;height:40px;border-radius:12px;
  background:linear-gradient(135deg,rgba(34,211,238,.16),rgba(167,139,250,.16));
  border:1px solid var(--line-strong);
  animation:pulse 3.8s ease-in-out infinite;
}
.logo::before{
  content:"";position:absolute;inset:11px;border-radius:3px;
  background:linear-gradient(135deg,var(--cyan),var(--violet));
  transform:rotate(45deg);
}
.logo::after{
  content:"";position:absolute;left:50%;top:50%;width:5px;height:5px;
  margin:-2.5px 0 0 -2.5px;border-radius:50%;background:var(--bg);
}
@keyframes pulse{
  0%,100%{box-shadow:0 0 14px rgba(34,211,238,.18),inset 0 0 12px rgba(34,211,238,.06)}
  50%{box-shadow:0 0 26px rgba(34,211,238,.40),inset 0 0 16px rgba(34,211,238,.14)}
}
@media (prefers-reduced-motion:reduce){.logo{animation:none}}
.titles{min-width:0}
.titles .en{
  margin:0 0 4px;font:600 .68rem/1 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  letter-spacing:.24em;color:var(--cyan);text-transform:uppercase;opacity:.9;
}
header.site h1{margin:0;font-size:1.66rem;font-weight:800;letter-spacing:-.01em;line-height:1.15}
header.site h1 a{
  background:linear-gradient(94deg,var(--cyan),#60a5fa 42%,var(--violet));
  -webkit-background-clip:text;background-clip:text;color:transparent;text-decoration:none;
}
.stats{
  display:flex;flex-wrap:wrap;gap:9px;margin:16px 0 0;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.78rem;
}
.stats span{
  padding:3px 11px;border-radius:9px;color:var(--muted);
  border:1px solid var(--line);background:var(--tag);white-space:nowrap;
}
.stats b{
  font-weight:700;
  background:linear-gradient(var(--cyan),var(--violet));
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
header.site .desc{margin:14px 0 0;color:var(--muted);font-size:.9rem;max-width:62ch}
header.site nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
header.site nav a{
  padding:4px 13px;border-radius:999px;font-size:.84rem;color:var(--muted);
  border:1px solid var(--line);background:var(--tag);text-decoration:none;
  transition:color .16s,border-color .16s,background .16s,box-shadow .16s;
}
header.site nav a:hover{
  color:var(--fg);border-color:var(--line-strong);
  background:rgba(34,211,238,.10);box-shadow:0 0 0 1px rgba(34,211,238,.18) inset;
}
a{color:var(--link);text-decoration:none;transition:color .15s}
a:hover{color:var(--link-hover);text-decoration:underline;text-underline-offset:3px}
h1{font-size:1.55rem;line-height:1.35;letter-spacing:-.01em;margin:0 0 8px}
h2{
  display:flex;align-items:center;gap:12px;
  font-size:1.1rem;font-weight:700;letter-spacing:.01em;
  margin:42px 0 16px;padding-bottom:11px;border-bottom:1px solid var(--line);
}
h2::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--line-strong),transparent)}
h3{font-size:1.01rem;font-weight:600;margin:0 0 7px;line-height:1.5}
.meta{
  display:flex;flex-wrap:wrap;align-items:center;gap:6px;
  margin:0 0 9px;font-size:.8rem;color:var(--muted);
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
.sum{margin:0 0 5px;font-size:.94rem}
.why{margin:0;font-size:.9rem;color:var(--muted)}
.dup{color:var(--muted);font-size:.82rem;margin:8px 0 0;opacity:.85}
.pick,.item{
  position:relative;overflow:hidden;
  background:var(--card);border:1px solid var(--card-line);border-radius:14px;
  padding:15px 17px;margin:0 0 12px;
  transition:border-color .18s,transform .18s,box-shadow .18s;
}
.pick:hover,.item:hover{
  border-color:var(--line-strong);transform:translateY(-2px);
  box-shadow:var(--shadow),0 0 22px rgba(34,211,238,.16);
}
.pick{padding-left:20px}
.pick::before{
  content:"";position:absolute;left:0;top:14px;bottom:14px;width:2px;border-radius:2px;
  background:linear-gradient(var(--cyan),var(--violet));
}
.num{
  display:inline-block;min-width:1.9em;
  font:800 .92rem/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  background:linear-gradient(var(--cyan),var(--violet));
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
.tag{
  display:inline-block;padding:1px 8px;border-radius:6px;
  background:var(--tag);border:1px solid transparent;
  font:500 .75rem/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  color:var(--muted);white-space:nowrap;
}
.tag.src{color:var(--fg);border-color:var(--line)}
article[data-src=github] .tag.src{color:#c4b5fd;border-color:rgba(196,181,253,.35)}
article[data-src=youtube] .tag.src{color:#fda4af;border-color:rgba(253,164,175,.35)}
article[data-src=paper] .tag.src{color:#93c5fd;border-color:rgba(147,197,253,.35)}
article[data-src=blog] .tag.src{color:#6ee7b7;border-color:rgba(110,231,183,.35)}
article[data-src=hackernews] .tag.src{color:#fcd34d;border-color:rgba(252,211,77,.35)}
.date{
  margin-left:auto;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:.76rem;color:var(--muted);opacity:.75;
}
blockquote{
  margin:0 0 24px;padding:12px 16px;border-radius:0 12px 12px 0;
  border-left:2px solid var(--line-strong);background:var(--tag);
  color:var(--muted);font-size:.88rem;
}
blockquote p{margin:0}
.warn{
  margin:0 0 24px;padding:13px 17px;border-radius:12px;font-size:.88rem;
  background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.28);
  border-left:2px solid #fbbf24;
}
.warn strong{color:#fcd34d}
.warn p{margin:0}
.warn ul{margin:8px 0 0;padding-left:20px}
.warn li{margin:2px 0}
footer{
  margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
  color:var(--muted);font-size:.82rem;line-height:1.7;
}
footer p{margin:0}
.months h3{
  margin:26px 0 10px;font-weight:600;font-size:.86rem;letter-spacing:.08em;
  text-transform:uppercase;color:var(--cyan);opacity:.85;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
.archive-list{list-style:none;padding:0;margin:0}
.archive-list li{
  display:flex;align-items:baseline;gap:12px;
  padding:9px 4px;border-bottom:1px solid var(--line);font-size:.95rem;
}
.archive-list li:hover{background:rgba(34,211,238,.05)}
.archive-list .cnt{
  margin-left:auto;color:var(--muted);font-size:.8rem;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:52%;
}
code{
  padding:1px 6px;border-radius:6px;background:var(--tag);
  font:400 .85em/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
.pager{display:flex;justify-content:space-between;font-size:.9rem;margin:28px 0}
@media(max-width:560px){
  .wrap{padding:24px 15px 64px}
  header.site h1{font-size:1.36rem}
  .logo{width:34px;height:34px;border-radius:10px}
  .logo::before{inset:9px}
  .titles .en{font-size:.62rem;letter-spacing:.18em}
  h1{font-size:1.3rem}
  .pick,.item{padding:13px 14px}
  .pick{padding-left:17px}
  .archive-list .cnt{max-width:100%;display:block;margin:2px 0 0}
  .archive-list li{flex-wrap:wrap}
}
"""


def esc(s):
    return html.escape(s or "", quote=True)


def parse_dt(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_all():
    out = []
    for p in sorted(DIGEST_DIR.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 读取失败 {p.name}: {e}")
    return out


def load_weeklies():
    out = []
    if not WEEKLY_DIR.exists():
        return out
    for p in sorted(WEEKLY_DIR.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 读取失败 {p.name}: {e}")
    return out


def week_of(date_s):
    """由日期字符串推出 ISO 周号，用于互链。"""
    dt = parse_dt(date_s)
    if not dt:
        return ""
    y, w, _ = dt.astimezone(CST).isocalendar()
    return f"{y}-W{w:02d}"


def badges(it):
    ex = it.get("extra") or {}
    src = it.get("source")
    b = []
    if src == "github":
        b.append(f"⭐ {ex.get('stars', 0)}")
        if ex.get("language"):
            b.append(esc(ex["language"]))
        if ex.get("created"):
            b.append(f"新建 {esc(ex['created'])}")
    elif src == "hackernews":
        b.append(f"🔥 {ex.get('points', 0)} 分")
        b.append(f"💬 {ex.get('comments', 0)}")
    elif src == "paper":
        b.append(f"👍 {ex['upvotes']}" if ex.get("upvotes") else "论文")
    elif src == "youtube":
        b.append("视频")
    else:
        b.append("文章")
    return b


def item_html(it, idx=None, cls="item"):
    dt = parse_dt(it.get("dt"))
    date_s = dt.astimezone(CST).strftime("%m-%d") if dt else ""
    src = it.get("source") or ""
    tags = "".join(f'<span class="tag">{t}</span>' for t in badges(it))
    num = f'<span class="num">{idx:02d}</span> ' if idx else ""
    head = (
        f'<h3>{num}<a href="{esc(it.get("link"))}" target="_blank" '
        f'rel="noopener">{esc(it.get("title"))}</a></h3>'
    )
    parts = [
        f'<article class="{cls}" data-src="{esc(src)}">',
        head,
        f'<p class="meta"><span class="tag src">{esc(it.get("source_label"))}</span>'
        f'{tags}<span class="date">{date_s}</span></p>',
    ]
    if it.get("summary_zh"):
        parts.append(f'<p class="sum">{esc(it["summary_zh"])}</p>')
    elif it.get("summary"):
        parts.append(f'<p class="sum">{esc(it["summary"][:260])}</p>')
    if it.get("why_zh"):
        parts.append(f'<p class="why">为什么值得看：{esc(it["why_zh"])}</p>')
    if it.get("dup_note"):
        parts.append(f'<p class="dup">🔁 {esc(it["dup_note"])}</p>')
    parts.append("</article>")
    return "\n".join(parts)


def page(title, body, desc="", canonical="", rel_root="", extra_head="", stats=""):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{extra_head}<link rel="stylesheet" href="{rel_root}style.css">
<link rel="alternate" type="application/rss+xml" title="{esc(SITE_TITLE)}" href="{SITE_URL}/feed.xml">
</head>
<body>
<div class="wrap">
<header class="site">
<div class="brand">
<span class="logo" aria-hidden="true"></span>
<div class="titles">
<p class="en">AI Frontier Digest</p>
<h1><a href="{rel_root}">{esc(SITE_TITLE)}</a></h1>
</div>
</div>
<p class="desc">{esc(SITE_DESC)}</p>
{stats}<nav><a href="{rel_root}">最新</a><a href="{rel_root}archive">归档</a><a href="{rel_root}feed.xml">RSS</a><a href="{rel_root}about">关于</a></nav>
</header>
{body}
<footer>
<p>{esc(SITE_TITLE)} · 由 GitHub Actions 每天 16:00 (CST) 自动生成 · 内容版权归原作者所有，链接均为原始出处</p>
</footer>
</div>
</body>
</html>
"""


def stats_bar(*pairs):
    """数据条：stats_bar(('今日', 14, '条'), ('源', 5, '个'))"""
    if not pairs:
        return ""
    inner = "".join(
        f"<span>{esc(label)} <b>{esc(str(val))}</b> {esc(unit)}</span>"
        for label, val, unit in pairs
    )
    return f'<div class="stats">{inner}</div>'


def render_digest(d, rel_root="", canonical="", week="", total_days=0):
    items = d.get("items") or []
    dups = d.get("dups") or []
    cnt = d.get("source_count") or {}
    fails = d.get("failures") or {}
    ferrs = d.get("failure_errors") or {}

    stats = stats_bar(
        ("今日", len(items) + len(dups), "条"),
        ("源", len(cnt), "个"),
        ("累计", total_days, "期"),
    )
    body = [f'<h1>{esc(d.get("date"))} 日报</h1>']
    meta = f'生成时间 {esc(d.get("generated"))} (CST) ｜ 共 {len(items) + len(dups)} 条'
    if dups:
        meta += f'（新增 {len(items)} · 重复/相似 {len(dups)}）'
    if week:
        meta += f'　｜　<a href="{rel_root}w/{esc(week)}">本周精选 →</a>'
    body.append(f'<p class="meta">{meta}</p>')
    if cnt:
        body.append(
            '<p class="meta">源命中数：'
            + " · ".join(f"{esc(SRC_NAME.get(k, k))} {v}" for k, v in cnt.items())
            + "</p>"
        )

    if fails:
        lis = ""
        for h, n in sorted(fails.items()):
            err = ferrs.get(h)
            lis += (
                f"<li><code>{esc(h)}</code> — 失败 {n} 次"
                + (f"（{esc(err)}）" if err else "")
                + "</li>"
            )
        body.append(
            '<div class="warn"><strong>⚠️ 数据源访问异常</strong>'
            "<p>本次运行中以下站点访问失败，对应内容可能缺失：</p>"
            f"<ul>{lis}</ul></div>"
        )

    top_n = min(6, len(items))
    if top_n:
        body.append(f"<h2>📌 今日精选 Top {top_n}</h2>")
        for i, it in enumerate(items[:top_n], 1):
            body.append(item_html(it, idx=i, cls="pick"))

    for key in ("github", "youtube", "paper", "blog", "hackernews"):
        group = [i for i in items[top_n:] if i.get("source") == key]
        if not group:
            continue
        body.append(f"<h2>{SRC_ICON[key]} {SRC_NAME[key]}（{len(group)}）</h2>")
        for it in group:
            body.append(item_html(it))

    if dups:
        body.append(f"<h2>🔁 重复 / 相似提醒（{len(dups)}）</h2>")
        body.append(
            "<blockquote><p>以下条目此前推荐过，或与历史条目高度相似，仅列出供参考。</p></blockquote>"
        )
        for it in dups:
            body.append(item_html(it, cls="item"))

    if canonical:
        body.append(f'<p class="meta" style="margin-top:26px">永久链接：<a href="{esc(canonical)}">{esc(canonical)}</a></p>')

    return page(
        f'{d.get("date")} · {SITE_TITLE}',
        "\n".join(body),
        desc=f'{d.get("date")} AI / LLM / Agent 前沿日报',
        canonical=canonical,
        rel_root=rel_root,
        stats=stats,
    )


def render_weekly(w, rel_root="", total_days=0):
    items = w.get("items") or []
    body = [f'<h1>本周精选 · {esc(w.get("week"))}</h1>']
    body.append(
        f'<p class="meta">覆盖 {esc(w.get("start"))} ~ {esc(w.get("end"))}'
        f'　｜　共 {len(items)} 条　｜　生成 {esc(w.get("generated"))} (CST)</p>'
    )
    for i, it in enumerate(items, 1):
        body.append(item_html(it, idx=i, cls="pick"))
    return page(
        f'本周精选 {w.get("week")} · ' + SITE_TITLE,
        "\n".join(body),
        desc=f'{w.get("start")} ~ {w.get("end")} AI / LLM / Agent 本周精选',
        rel_root=rel_root,
        stats=stats_bar(
            ("本期", len(items), "条"),
            ("累计", total_days, "期"),
        ),
    )


def render_archive(all_d, all_w):
    body = ["<h1>历史归档</h1>"]
    if all_w:
        body.append('<div class="months"><h3>📌 周报</h3><ul class="archive-list">')
        for w in all_w:
            n = len(w.get("items") or [])
            top = (w.get("items") or [{}])[0].get("title") if w.get("items") else ""
            body.append(
                f'<li><a href="w/{esc(w.get("week"))}">'
                f'{esc(w.get("start"))} ~ {esc(w.get("end"))}</a>'
                f'<span class="cnt">{n} 条 · {esc((top or "")[:46])}</span></li>'
            )
        body.append("</ul></div>")
    months = {}
    for d in all_d:
        months.setdefault((d.get("date") or "")[:7], []).append(d)
    for m in sorted(months, reverse=True):
        body.append(f'<div class="months"><h3>{esc(m)}</h3><ul class="archive-list">')
        for d in months[m]:
            n = len(d.get("items") or [])
            top = (d.get("items") or [{}])[0].get("title") if d.get("items") else ""
            body.append(
                f'<li><a href="d/{esc(d.get("date"))}">{esc(d.get("date"))}</a>'
                f'<span class="cnt">{n} 条 · {esc((top or "")[:46])}</span></li>'
            )
        body.append("</ul></div>")
    total_items = sum(len(d.get("items") or []) for d in all_d)
    return page(
        "历史归档 · " + SITE_TITLE,
        "\n".join(body),
        desc="历史归档",
        stats=stats_bar(
            ("累计", len(all_d), "期"),
            ("条目", total_items, "条"),
            ("周报", len(all_w), "期"),
        ),
    )


def render_about(all_d, all_w):
    body = [
        "<h1>关于</h1>",
        f"<p>{esc(SITE_DESC)}</p>",
        "<h2>数据源</h2>",
        "<ul>"
        "<li><strong>GitHub</strong>：最近 45 天新建、按星数排序的 llm / ai-agents / mcp / rag 等 topic 仓库</li>"
        "<li><strong>YouTube</strong>：OpenAI、Anthropic、DeepMind、LangChain、Karpathy 等 16 个频道的更新</li>"
        "<li><strong>博客</strong>：OpenAI / DeepMind / HuggingFace / LangChain 官方、Simon Willison、"
        "Lilian Weng、The Gradient、Interconnects、Latent Space、新智元、量子位等 22 个源</li>"
        "<li><strong>论文</strong>：HuggingFace Daily Papers、arXiv cs.AI / cs.CL</li>"
        "<li><strong>官方页</strong>：Anthropic news / engineering（无 RSS，直接抓页面）</li>"
        "<li><strong>社区</strong>：Hacker News 高分讨论</li>"
        "</ul>",
        "<h2>怎么做的</h2>",
        "<p>每天 16:00（北京时间）由 GitHub Actions 自动采集，"
        "按来源配额与关键词打分排序，用大模型生成中文摘要，"
        "并与历史记录比对去重、标记相似内容。</p>",
        "<h2>订阅</h2>",
        f'<p>RSS：<a href="{SITE_URL}/feed.xml">{SITE_URL}/feed.xml</a></p>',
        f'<p>全部内容归档在 <a href="https://github.com/Justin-Yijun/ai-daily-digest" '
        f'target="_blank" rel="noopener">GitHub 仓库</a>。</p>',
    ]
    if all_d:
        body.append(f"<p>已累计 {len(all_d)} 期日报" + (f"、{len(all_w)} 期周报" if all_w else "") + "。</p>")
    return page("关于 · " + SITE_TITLE, "\n".join(body), desc="关于 " + SITE_TITLE)


def render_feed(all_d):
    # lastBuildDate 用最新一期的生成时间，保证同一批数据重复构建结果完全一致（幂等）
    now = parse_dt(all_d[0].get("generated")) or datetime.now(timezone.utc)
    items = []
    for d in all_d[:40]:
        date_s = d.get("date") or ""
        dt = parse_dt(date_s)
        picks = (d.get("items") or [])[:6]
        desc = "".join(
            f'<li><a href="{esc(p.get("link"))}">{esc(p.get("title"))}</a>'
            + (f" — {esc(p.get('summary_zh'))}" if p.get("summary_zh") else "")
            + "</li>"
            for p in picks
        )
        items.append(
            "<item>"
            f"<title>{esc(date_s)} AI 前沿日报</title>"
            f"<link>{SITE_URL}/d/{esc(date_s)}</link>"
            f"<guid isPermaLink=\"true\">{SITE_URL}/d/{esc(date_s)}</guid>"
            + (f"<pubDate>{format_datetime(dt)}</pubDate>" if dt else "")
            + f"<description><![CDATA[<p>{esc(d.get('date'))} 精选：</p><ul>{desc}</ul>"
            f'<p><a href="{SITE_URL}/d/{esc(date_s)}">阅读完整日报</a></p>]]></description>'
            "</item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
        f"<title>{esc(SITE_TITLE)}</title>\n"
        f"<link>{SITE_URL}/</link>\n"
        f"<description>{esc(SITE_DESC)}</description>\n"
        "<language>zh-cn</language>\n"
        f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>\n"
        f'<atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items)
        + "\n</channel>\n</rss>\n"
    )
    return xml


def main():
    all_d = load_all()
    all_w = load_weeklies()
    have_w = {w.get("week") for w in all_w}
    print(f"[site] 读到 {len(all_d)} 期日报、{len(all_w)} 期周报")
    if not all_d:
        print("[site] 没有 digest/*.json，先跑 collect.py")
        return

    (SITE_DIR / "d").mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "style.css").write_text(STYLE, encoding="utf-8")

    for i, d in enumerate(all_d):
        date_s = d.get("date") or f"unknown-{i}"
        canonical = f"{SITE_URL}/d/{date_s}"
        wk = week_of(date_s)
        if wk not in have_w:
            wk = ""  # 没有对应的周报页就不放链接，避免死链
        (SITE_DIR / "d" / f"{date_s}.html").write_text(
            render_digest(
                d, rel_root="../", canonical=canonical, week=wk, total_days=len(all_d)
            ),
            encoding="utf-8",
        )

    latest_wk = week_of(all_d[0].get("date") or "")
    if latest_wk not in have_w:
        latest_wk = ""
    (SITE_DIR / "index.html").write_text(
        render_digest(all_d[0], rel_root="", week=latest_wk, total_days=len(all_d)),
        encoding="utf-8",
    )

    if all_w:
        (SITE_DIR / "w").mkdir(parents=True, exist_ok=True)
        for w in all_w:
            (SITE_DIR / "w" / f"{w.get('week')}.html").write_text(
                render_weekly(w, rel_root="../", total_days=len(all_w)),
                encoding="utf-8",
            )

    (SITE_DIR / "archive.html").write_text(render_archive(all_d, all_w), encoding="utf-8")
    (SITE_DIR / "about.html").write_text(render_about(all_d, all_w), encoding="utf-8")
    (SITE_DIR / "feed.xml").write_text(render_feed(all_d), encoding="utf-8")
    (SITE_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8"
    )
    urls = [f"{SITE_URL}/", f"{SITE_URL}/archive", f"{SITE_URL}/about"]
    urls += [f"{SITE_URL}/d/{d.get('date')}" for d in all_d]
    urls += [f"{SITE_URL}/w/{w.get('week')}" for w in all_w]
    (SITE_DIR / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(f"<url><loc>{u}</loc></url>" for u in urls)
        + "\n</urlset>\n",
        encoding="utf-8",
    )
    print(
        f"[site] 已生成 {SITE_DIR}（首页 + {len(all_d)} 期日报"
        + (f" + {len(all_w)} 期周报" if all_w else "")
        + " + 归档 + RSS + sitemap）"
    )


if __name__ == "__main__":
    main()
