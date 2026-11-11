# -*- coding: utf-8 -*-
"""
考研英语（一）2017-2026 十年真题词频统计

用法:
    python scripts/build_word_frequency.py

输入: 10年真题/*.md
输出: output/ 下的 CSV、Excel 与 HTML 报告
"""

from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter, OrderedDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "10年真题"
OUT_DIR = BASE_DIR / "output"

# ---------------------------------------------------------------- 分词规则
# 英文单词：允许词内连字符与撇号（Parkrun's / well-paid / don't）
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*(?:-[A-Za-z]+)*")
HEADING_RE = re.compile(r"^(#{1,6})\s*(.*?)\s*$")
NUMBERED_RE = re.compile(r"^\d{1,3}\.\s")
OPTION_RE = re.compile(r"^\[[A-G]\]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

STOPWORDS = set(
    """a about above after again against all also am an and any are aren't as at be
    because been before being below between both but by can cannot could couldn't did
    didn't do does doesn't doing don't down during each either few for from further had
    hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself
    him himself his how how's however i i'd i'll i'm i've if in into is isn't it it's its
    itself just let's many may me might more most much must mustn't my myself neither no
    nor not now of off on once one only or other ought our ours ourselves out over own
    per same shall shan't she she'd she'll she's should shouldn't since so some such than
    that that's the their theirs them themselves then there there's these they they'd
    they'll they're they've this those though through thus to too under until up upon us
    very was wasn't we we'd we'll we're we've were weren't what what's when when's where
    where's whether which while who who's whom whose why why's will with within without
    won't would wouldn't yet you you'd you'll you're you've your yours yourself yourselves
    s t d ll re ve m""".split()
)


def tokenize(text: str) -> list[str]:
    """把一段英文拆成小写单词列表。"""
    words = []
    for raw in TOKEN_RE.findall(text.replace("’", "'")):
        w = raw.lower()
        # 去掉所有格与缩写尾巴：parkrun's -> parkrun, kids' -> kids
        if w.endswith("'s"):
            w = w[:-2]
        elif w.endswith("'"):
            w = w[:-1]
        if len(w) < 2:          # 单字母（选项标号、冠词 a/i 等）不计
            continue
        words.append(w)
    return words


# ---------------------------------------------------------------- 试卷解析
SECTION_ORDER = ["完形填空", "阅读 Text 1", "阅读 Text 2", "阅读 Text 3",
                 "阅读 Text 4", "新题型", "翻译", "写作题干"]


class PaperParser:
    """按标题层级切分试卷，并给每个段落打上「年份 / 题型 / 段落类别」标签。

    段落类别：
        body       —— 文章正文（完形文章、阅读文章、新题型文章、翻译原文）
        stem       —— 题干（选择题问题部分）
        option     —— 选项（[A] [B] [C] [D] 等）
        directions —— 考试指令（Directions 说明文字，10 年高度重复）
    """

    def __init__(self, year: int):
        self.year = year
        self.section = "完形填空"
        self.part = None
        self.text_no = None
        self.in_directions = False
        self.records: list[dict] = []

    # -- 上下文 ---------------------------------------------------
    def _label(self) -> str:
        if self.section == "阅读理解":
            if self.part == "B":
                return "新题型"
            if self.text_no:
                return f"阅读 Text {self.text_no}"
            return "阅读 Text 1"
        return self.section

    def _on_heading(self, title: str) -> None:
        low = title.lower()
        if "use of english" in low:
            self.section, self.part, self.text_no = "完形填空", None, None
            self.in_directions = False
        elif "reading comprehension" in low:
            self.section, self.part, self.text_no = "阅读理解", "A", None
            self.in_directions = False
        elif "translation" in low:
            self.section, self.part, self.text_no = "翻译", None, None
            self.in_directions = False
        elif "writing" in low:
            self.section, self.part, self.text_no = "写作", None, None
            self.in_directions = False
        elif low.startswith("part a"):
            self.part = "A"
        elif low.startswith("part b"):
            self.part = "B"
        elif re.match(r"^text\s*\d", low):
            self.part = "A"
            self.text_no = int(re.search(r"\d+", low).group())
        elif "directions" in low:
            self.in_directions = True
        else:
            # 真实文章标题（如 "Five ways to make conversation with anyone"）
            self._add(title, "body")

    def _add(self, text: str, category: str) -> None:
        if CJK_RE.search(text):
            return  # 中文注释行，跳过
        words = tokenize(text)
        if words:
            self.records.append({
                "year": self.year,
                "section": self._label(),
                "category": category,
                "words": words,
            })

    # -- 入口 -----------------------------------------------------
    def parse(self, md_text: str) -> list[dict]:
        buffer: list[str] = []

        def flush() -> None:
            if not buffer:
                return
            para = " ".join(buffer).strip()
            buffer.clear()
            if not para:
                return
            if self.in_directions:
                cat = "directions"
                if re.search(r"\(\d+\s*points\)", para):
                    self.in_directions = False   # Directions 段以 (N points) 结尾
            elif NUMBERED_RE.match(para) or OPTION_RE.match(para):
                # 以 "21." 开头的是题干；以 "[A]" 开头的是选项
                cat = "option" if OPTION_RE.match(para) else "stem"
            else:
                cat = "body"
            self._add(para, cat)

        for raw in md_text.splitlines():
            line = raw.rstrip()
            if not line.strip() or line.strip() in {"---", "***", "___"}:
                flush()
                continue
            m = HEADING_RE.match(line)
            if m:
                flush()
                self._on_heading(m.group(2))
                continue
            buffer.append(line.strip())
        flush()
        return self.records


def load_corpus() -> tuple[list[dict], list[int]]:
    files = sorted(SRC_DIR.glob("*.md"))
    if not files:
        raise SystemExit(f"未找到试卷文件: {SRC_DIR}")
    records: list[dict] = []
    for f in files:
        year = int(re.search(r"(\d{4})", f.name).group(1))
        records.extend(PaperParser(year).parse(f.read_text(encoding="utf-8")))
    years = sorted({f.name for f in files})
    years = sorted(int(re.search(r"(\d{4})", n).group(1)) for n in years)
    return records, years


# ---------------------------------------------------------------- 统计汇总
def build_stats(records: list[dict], years: list[int]) -> dict:
    full = Counter()
    body = Counter()
    per_year = {y: Counter() for y in years}
    per_year_body = {y: Counter() for y in years}
    per_section = Counter()
    section_tokens = Counter()
    cat_tokens = Counter()

    for rec in records:
        c = Counter(rec["words"])
        cat_tokens[rec["category"]] += len(rec["words"])
        section_tokens[rec["section"]] += len(rec["words"])
        full.update(c)
        per_year[rec["year"]].update(c)
        per_section[rec["section"]] += sum(c.values())
        if rec["category"] == "body":
            body.update(c)
            per_year_body[rec["year"]].update(c)

    return {
        "full": full,
        "body": body,
        "per_year": per_year,
        "per_year_body": per_year_body,
        "section_tokens": section_tokens,
        "section_types": per_section,
        "cat_tokens": cat_tokens,
    }


def ranked_rows(counter: Counter, years: list[int], per_year: dict | None = None):
    """返回按词频降序、同频按字母升序的表格行。"""
    rows = []
    total = sum(counter.values()) or 1
    for rank, (word, cnt) in enumerate(
            sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])), start=1):
        yc = [per_year[y][word] if per_year else 0 for y in years] if per_year else []
        rows.append({
            "rank": rank,
            "word": word,
            "count": cnt,
            "share": cnt / total,
            "years_seen": sum(1 for v in yc if v > 0) if per_year else 0,
            "by_year": yc,
            "is_stop": word in STOPWORDS,
        })
    return rows


def renumber(rows: list[dict]) -> list[dict]:
    """过滤掉功能词后重新编排连续名次。"""
    return [{**r, "rank": i} for i, r in enumerate(rows, start=1)]


def coverage(counter: Counter, thresholds=(0.5, 0.8, 0.9, 0.95)) -> dict:
    total = sum(counter.values()) or 1
    ordered = sorted(counter.values(), reverse=True)
    result, cum, idx = {}, 0, 0
    for t in thresholds:
        while idx < len(ordered) and cum / total < t:
            cum += ordered[idx]
            idx += 1
        result[t] = idx
    return result


def summary(records, stats, years) -> dict:
    full = stats["full"]
    total_words = sum(full.values())
    return {
        "papers": len(years),
        "years": years,
        "total_words": total_words,
        "unique_words": len(full),
        "body_words": sum(stats["body"].values()),
        "body_unique": len(stats["body"]),
        "content_words": sum(v for w, v in stats["body"].items() if w not in STOPWORDS),
        "content_unique": sum(1 for w in stats["body"] if w not in STOPWORDS),
        "hapax": sum(1 for v in full.values() if v == 1),
        "coverage": {str(k): v for k, v in coverage(full).items()},
        "coverage_body": {str(k): v for k, v in coverage(stats["body"]).items()},
        "cat_tokens": dict(stats["cat_tokens"]),
        "section_tokens": dict(stats["section_tokens"]),
        "per_year": {
            str(y): {
                "total": sum(stats["per_year"][y].values()),
                "unique": len(stats["per_year"][y]),
                "body": sum(stats["per_year_body"][y].values()),
                "top": stats["per_year"][y].most_common(1)[0][0] if stats["per_year"][y] else "",
            } for y in years
        },
    }


# ---------------------------------------------------------------- 输出: CSV
def write_csv(path: Path, rows: list[dict], years: list[int], with_year: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        header = ["排名", "单词", "词频", "占比(%)", "出现年份数"]
        if with_year:
            header += [f"{y}年" for y in years]
        header += ["类型"]
        w.writerow(header)
        for r in rows:
            line = [r["rank"], r["word"], r["count"], f"{r['share'] * 100:.4f}",
                    r["years_seen"]]
            if with_year:
                line += r["by_year"]
            line.append("功能词" if r["is_stop"] else "实词")
            w.writerow(line)


# ---------------------------------------------------------------- 输出: XLSX
def write_xlsx(path: Path, data: dict) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    years = data["years"]
    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="1F4E79")
    head_font = Font(color="FFFFFF", bold=True, size=11)
    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center")

    def style_sheet(ws, widths, freeze="A2"):
        for i, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width
        for cell in ws[1]:
            cell.fill = head_fill
            cell.font = head_font
            cell.alignment = center
        ws.freeze_panes = freeze
        ws.row_dimensions[1].height = 22
        ws.auto_filter.ref = ws.dimensions

    # --- 说明
    ws = wb.active
    ws.title = "统计说明"
    s = data["summary"]
    info = [
        ("考研英语（一）十年真题词频统计", ""),
        ("语料范围", f"{s['years'][0]}—{s['years'][-1]} 年共 {s['papers']} 套试卷（10年真题/*.md）"),
        ("统计口径", "将 10 套试卷合并为一个大文本后统一分词计数"),
        ("总词数（token）", f"{s['total_words']:,}"),
        ("不同单词数（type）", f"{s['unique_words']:,}"),
        ("文章正文词数", f"{s['body_words']:,}（不同单词 {s['body_unique']:,}）"),
        ("实词词数", f"{s['content_words']:,}（不同单词 {s['content_unique']:,}）"),
        ("只出现 1 次的单词", f"{s['hapax']:,}"),
        ("覆盖 50% 正文所需的单词数", f"{s['coverage_body']['0.5']:,}"),
        ("覆盖 80% 正文所需的单词数", f"{s['coverage_body']['0.8']:,}"),
        ("覆盖 90% 正文所需的单词数", f"{s['coverage_body']['0.9']:,}"),
        ("覆盖 95% 正文所需的单词数", f"{s['coverage_body']['0.95']:,}"),
        ("占比说明", f"各表占比均以该表统计范围的总词数为分母（全量表 {s['total_words']:,}，"
                     f"正文表 {s['body_words']:,}）"),
        ("分词规则", "仅统计英文字母构成的单词；忽略数字、标点、选项标号；"
                     "连字符词（well-paid）与缩写（don't）视为一个词；"
                     "所有格（Parkrun's）归为词根（parkrun）；统一小写；不区分词形（work/works/working 分开统计）"),
        ("工作表说明", "全量词频＝正文＋题干＋选项＋指令；正文词频＝仅文章正文；"
                       "实词词频＝在正文基础上剔除 the/a/of 等高频功能词后的可背单词"),
    ]
    for r, (k, v) in enumerate(info, start=1):
        ws.cell(r, 1, k)
        ws.cell(r, 2, v)
        ws.cell(r, 1).font = Font(bold=True)
        ws.cell(r, 2).alignment = Alignment(vertical="center", wrap_text=True)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 110
    ws["A1"].font = Font(bold=True, size=14, color="1F4E79")

    # --- 全量词频
    def freq_sheet(title, rows, with_year=True, highlight_stop=False):
        ws = wb.create_sheet(title)
        header = ["排名", "单词", "词频", "占比(%)", "出现年份数"]
        if with_year:
            header += [f"{y}年" for y in years]
        header.append("类型")
        ws.append(header)
        for r in rows:
            line = [r["rank"], r["word"], r["count"], round(r["share"] * 100, 4), r["years_seen"]]
            if with_year:
                line += r["by_year"]
            line.append("功能词" if r["is_stop"] else "实词")
            ws.append(line)
        widths = [8, 18, 9, 10, 12] + ([9] * len(years) if with_year else []) + [9]
        style_sheet(ws, widths)
        if highlight_stop:
            gray = Font(color="A6A6A6")
            for row in ws.iter_rows(min_row=2):
                if row[-1].value == "功能词":
                    for cell in row:
                        cell.font = gray
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.border = border
                cell.alignment = Alignment(horizontal="center")
        return ws

    freq_sheet("全量词频", data["rows_full"])
    freq_sheet("正文词频", data["rows_body"], with_year=True)
    freq_sheet("实词词频", renumber([r for r in data["rows_body"] if not r["is_stop"]]))

    # --- 分年份
    ws = wb.create_sheet("分年份概览")
    ws.append(["年份", "试卷总词数", "不同单词数", "文章正文词数", "最高频单词"])
    s = data["summary"]
    for y in years:
        info = s["per_year"][str(y)]
        ws.append([y, info["total"], info["unique"], info["body"], info["top"]])
    style_sheet(ws, [10, 14, 14, 16, 16])

    # --- 分题型
    ws = wb.create_sheet("分题型概览")
    ws.append(["题型", "词数"])
    for name in SECTION_ORDER + [k for k in data["stats"]["section_tokens"] if k not in SECTION_ORDER]:
        if name in data["stats"]["section_tokens"]:
            ws.append([name, data["stats"]["section_tokens"][name]])
    style_sheet(ws, [18, 12])

    wb.save(path)


# ---------------------------------------------------------------- 输出: HTML
def write_html(path: Path, data: dict) -> None:
    s = data["summary"]
    years = data["years"]
    rows_full = data["rows_full"]
    rows_content = renumber([r for r in data["rows_body"] if not r["is_stop"]])

    def bar_rows(items, total, limit=40):
        out = []
        for i, (w, c) in enumerate(items[:limit], start=1):
            pct = c / total * 100
            width = c / items[0][1] * 100
            out.append(
                f'<div class="bar-row"><span class="bar-rank">{i}</span>'
                f'<span class="bar-word">{html.escape(w)}</span>'
                f'<span class="bar-track"><span class="bar-fill" style="width:{width:.1f}%"></span></span>'
                f'<span class="bar-num">{c}</span></div>'
            )
        return "\n".join(out)

    top_all = [(r["word"], r["count"]) for r in rows_full[:40]]
    top_content = [(r["word"], r["count"]) for r in rows_content[:40]]

    year_rows = "\n".join(
        f"<tr><td>{y}</td><td>{s['per_year'][str(y)]['total']:,}</td>"
        f"<td>{s['per_year'][str(y)]['unique']:,}</td>"
        f"<td>{s['per_year'][str(y)]['body']:,}</td>"
        f"<td class='word'>{html.escape(s['per_year'][str(y)]['top'])}</td></tr>"
        for y in years
    )

    section_rows = "\n".join(
        f"<tr><td>{html.escape(k)}</td><td>{v:,}</td></tr>"
        for k, v in sorted(data["stats"]["section_tokens"].items(),
                           key=lambda kv: -kv[1])
    )

    table_rows = "\n".join(
        f"<tr><td>{r['rank']}</td><td class='word'>{html.escape(r['word'])}</td>"
        f"<td>{r['count']}</td><td>{r['share'] * 100:.3f}%</td>"
        f"<td>{r['years_seen']}</td></tr>"
        for r in rows_content[:300]
    )

    cov = s["coverage_body"]
    total_body = s["body_words"]

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>考研英语（一）十年真题词频统计报告</title>
<style>
  :root {{
    --bg:#f5f7fa; --card:#ffffff; --ink:#1c2430; --sub:#6b7785;
    --line:#e6ebf1; --brand:#1f4e79; --accent:#2e86de; --warm:#e8873a;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
         line-height:1.65; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:56px 28px 80px; }}
  header {{ text-align:center; margin-bottom:44px; }}
  h1 {{ font-size:32px; margin:0 0 10px; letter-spacing:.5px; }}
  .sub {{ color:var(--sub); font-size:15px; }}
  h2 {{ font-size:20px; margin:0 0 6px; padding-left:12px;
        border-left:4px solid var(--brand); }}
  .note {{ color:var(--sub); font-size:13px; margin:0 0 20px; padding-left:16px; }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
             padding:28px 30px; margin-bottom:24px;
             box-shadow:0 1px 2px rgba(16,32,48,.04); }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
            gap:16px; margin-bottom:24px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
           padding:20px 22px; text-align:center; }}
  .card .k {{ font-size:26px; font-weight:700; color:var(--brand); font-variant-numeric:tabular-nums; }}
  .card .l {{ font-size:13px; color:var(--sub); margin-top:4px; }}
  .bar-row {{ display:grid; grid-template-columns:34px 130px 1fr 54px;
              align-items:center; gap:10px; padding:5px 0; font-size:14px; }}
  .bar-rank {{ color:var(--sub); font-size:12px; text-align:right; }}
  .bar-word {{ font-family:Consolas,"Courier New",monospace; font-weight:600;
               text-align:right; overflow:hidden; text-overflow:ellipsis; }}
  .bar-track {{ background:#eef2f7; border-radius:6px; height:14px; overflow:hidden; }}
  .bar-fill {{ display:block; height:100%; border-radius:6px;
               background:linear-gradient(90deg,#3f8fd6,#1f4e79); }}
  .bar-num {{ color:var(--sub); font-variant-numeric:tabular-nums; text-align:right; }}
  .cols {{ display:grid; grid-template-columns:1fr 1fr; gap:26px; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th,td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:center; }}
  th {{ background:#f0f5fb; color:var(--brand); font-weight:600; font-size:13px; }}
  td.word {{ font-family:Consolas,"Courier New",monospace; }}
  tbody tr:hover {{ background:#fafcff; }}
  .cover {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }}
  .cover div {{ text-align:center; background:#f7fafd; border:1px solid var(--line);
                border-radius:10px; padding:14px 8px; }}
  .cover b {{ display:block; font-size:22px; color:var(--warm); }}
  .cover span {{ font-size:12px; color:var(--sub); }}
  footer {{ text-align:center; color:var(--sub); font-size:12px; margin-top:36px; }}
  @media (max-width:760px) {{
    .cols {{ grid-template-columns:1fr; }}
    .cover {{ grid-template-columns:repeat(2,1fr); }}
    .bar-row {{ grid-template-columns:28px 96px 1fr 42px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>考研英语（一）十年真题词频统计</h1>
    <div class="sub">{years[0]}—{years[-1]} 年 · {s['papers']} 套试卷合并统计 · 共 {s['total_words']:,} 个单词，
    不同词形 {s['unique_words']:,} 个</div>
  </header>

  <div class="cards">
    <div class="card"><div class="k">{s['total_words']:,}</div><div class="l">总词数（含题干与选项）</div></div>
    <div class="card"><div class="k">{s['body_words']:,}</div><div class="l">文章正文词数</div></div>
    <div class="card"><div class="k">{s['unique_words']:,}</div><div class="l">不同词形总数</div></div>
    <div class="card"><div class="k">{s['content_unique']:,}</div><div class="l">不同实词数</div></div>
    <div class="card"><div class="k">{s['hapax']:,}</div><div class="l">只出现 1 次的词</div></div>
  </div>

  <section>
    <h2>背词效率：需要掌握多少词</h2>
    <p class="note">按正文词频从高到低累计，覆盖 {total_body:,} 个正文单词中的相应比例所需的单词个数。</p>
    <div class="cover">
      <div><b>{cov['0.5']:,}</b><span>覆盖 50% 正文</span></div>
      <div><b>{cov['0.8']:,}</b><span>覆盖 80% 正文</span></div>
      <div><b>{cov['0.9']:,}</b><span>覆盖 90% 正文</span></div>
      <div><b>{cov['0.95']:,}</b><span>覆盖 95% 正文</span></div>
    </div>
  </section>

  <section>
    <h2>全量最高频 40 词</h2>
    <p class="note">包含文章正文、题干、选项与考试指令，因此 the / a / of 等虚词排在前列。</p>
    {bar_rows(top_all, s['total_words'])}
  </section>

  <section>
    <h2>实词最高频 40 词</h2>
    <p class="note">已剔除 the、a、of、is 等功能词，统计范围为文章正文，更接近需要背诵的核心词汇。</p>
    {bar_rows(top_content, s['content_words'])}
  </section>

  <section>
    <h2>各年份词量</h2>
    <p class="note">同一年份内所有单词均计入，不同单词数反映该套试卷的词汇广度。</p>
    <table>
      <thead><tr><th>年份</th><th>总词数</th><th>不同单词数</th><th>正文词数</th><th>最高频单词</th></tr></thead>
      <tbody>{year_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>分题型词量</h2>
    <table>
      <thead><tr><th>题型</th><th>词数</th></tr></thead>
      <tbody>{section_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>实词词频总排行（前 300）</h2>
    <p class="note">完整 {s['content_unique']:,} 个实词见 Excel / CSV 文件。</p>
    <table>
      <thead><tr><th>排名</th><th>单词</th><th>词频</th><th>占比</th><th>出现年份</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>

  <footer>数据来源：10年真题/{years[0]}—{years[-1]}.md · 由 scripts/build_word_frequency.py 生成</footer>
</div>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")


# ---------------------------------------------------------------- 主流程
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records, years = load_corpus()
    stats = build_stats(records, years)

    rows_full = ranked_rows(stats["full"], years, stats["per_year"])
    rows_body = ranked_rows(stats["body"], years, stats["per_year_body"])

    data = {
        "years": years,
        "stats": stats,
        "rows_full": rows_full,
        "rows_body": rows_body,
        "summary": summary(records, stats, years),
    }
    data["summary"]["papers"] = len(records) and len(years)

    write_csv(OUT_DIR / "词频总表_全量.csv", rows_full, years, True)
    write_csv(OUT_DIR / "词频总表_正文.csv", rows_body, years, True)
    write_csv(OUT_DIR / "词频总表_实词.csv",
              renumber([r for r in rows_body if not r["is_stop"]]), years, True)
    write_xlsx(OUT_DIR / "考研英语一2017-2026词频总表.xlsx", data)
    write_html(OUT_DIR / "词频分析报告.html", data)

    s = data["summary"]
    print(f"试卷数        : {len(years)} ({years[0]}—{years[-1]})")
    print(f"总词数        : {s['total_words']:,}")
    print(f"不同词形      : {s['unique_words']:,}")
    print(f"正文词数      : {s['body_words']:,}")
    print(f"不同实词      : {s['content_unique']:,}")
    print(f"覆盖80%正文   : {s['coverage_body']['0.8']} 词")
    print("输出目录      :", OUT_DIR)


if __name__ == "__main__":
    main()
