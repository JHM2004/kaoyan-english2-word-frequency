# -*- coding: utf-8 -*-
"""
生成单词中文释义表 data/word_meanings.csv

释义来源：ECDICT 英汉词典（https://github.com/skywind3000/ECDICT，MIT License）
首次运行会把词典下载到 .cache/ecdict.csv（约 63MB），之后复用缓存。

用法:
    python scripts/build_word_meanings.py
"""

from __future__ import annotations

import csv
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_word_frequency import load_corpus, build_stats  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE = BASE_DIR / ".cache" / "ecdict.csv"
DICT_URL = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"
OUT = BASE_DIR / "data" / "word_meanings.csv"

# 词典未收录时的简单词形回退（只保留最常见的不规则变化）
IRREGULAR = {
    "went": "go", "gone": "go", "made": "make", "took": "take", "taken": "take",
    "found": "find", "felt": "feel", "became": "become", "began": "begin",
    "begun": "begin", "got": "get", "gotten": "get", "knew": "know", "known": "know",
    "saw": "see", "seen": "see", "gave": "give", "given": "give", "thought": "think",
    "brought": "bring", "bought": "buy", "held": "hold", "kept": "keep",
    "left": "leave", "led": "lead", "met": "meet", "paid": "pay", "ran": "run",
    "rose": "rise", "risen": "rise", "sent": "send", "spoke": "speak",
    "spoken": "speak", "spent": "spend", "stood": "stand", "told": "tell",
    "wrote": "write", "written": "write", "grew": "grow", "grown": "grow",
    "drew": "draw", "drawn": "draw", "drove": "drive", "driven": "drive",
    "ate": "eat", "eaten": "eat", "fell": "fall", "fallen": "fall",
    "forgot": "forget", "forgotten": "forget", "chose": "choose", "chosen": "choose",
    "wore": "wear", "worn": "wear", "won": "win", "lost": "lose", "built": "build",
    "heard": "hear", "meant": "mean", "sat": "sit", "slept": "sleep",
    "taught": "teach", "caught": "catch", "fought": "fight", "sought": "seek",
    "sold": "sell", "understood": "understand", "threw": "throw", "thrown": "throw",
    "children": "child", "people": "people", "men": "man", "women": "woman",
    "feet": "foot", "teeth": "tooth", "mice": "mouse", "data": "datum",
    "better": "good", "best": "good", "worse": "bad", "worst": "bad",
}

META_RE = re.compile(r"的(复数|单数|过去式|过去分词|现在式|现在时|过去时|现在分词|第三人称|名词复数|比较级|最高级)")
DOMAIN_RE = re.compile(r"^\[[^\]]+\]")
POS_RE = re.compile(r"^([a-zA-Z]+\.)\s*")

# 词典未收录的真题词（派生词、专有名词、新词），人工补齐
SUPPLEMENT = {
    "a-g": "选项标号 A—G",
    "acqui-hires": "人才收购（acqui-hire 的复数）",
    "baltimore-based": "总部位于巴尔的摩的",
    "brexit": "英国脱欧",
    "ccpa": "《加州消费者隐私法案》",
    "cofounded": "共同创办",
    "ferrovie": "意大利国家铁路公司（Ferrovie）",
    "festgoers": "参加节庆活动的人",
    "fitsmallbusiness": "FitSmallBusiness（美国商业资讯网站）",
    "graffitied": "被涂鸦的",
    "hgtv": "HGTV（美国家居与生活电视频道）",
    "homebuying": "购房",
    "housebuilding": "房屋建造",
    "inboxes": "收件箱",
    "inflation-adjusted": "经通胀调整的",
    "ipads": "iPad 平板电脑",
    "italiane": "意大利的（意大利语）",
    "ivywise": "IvyWise（美国升学咨询机构）",
    "livestream": "直播",
    "millennials": "千禧一代",
    "myjobquote": "MyJobQuote（英国装修报价网站）",
    "naismiths": "Naismiths（英国测量师行）",
    "oft-debated": "常被争论的",
    "outputted": "输出（output 的过去式）",
    "parkrun": "公园跑（英国免费社区跑步活动）",
    "personalisation": "个性化（英式拼写）",
    "plateaued": "进入平台期；趋于平稳",
    "preretirees": "临近退休者",
    "prosociality": "亲社会性",
    "reimagining": "重新构想",
    "reskilled": "经过再培训的",
    "reskilling": "再培训；技能再造",
    "retrospectons": "回顾；反思（原文拼写疑有误）",
    "rewilding": "再野化（生态修复）",
    "spammers": "垃圾信息发送者",
    "that'll": "that will 的缩写",
    "there'll": "there will 的缩写",
    "there're": "there are 的缩写",
    "tipflation": "小费通胀",
    "trenitalia": "意大利国铁（Trenitalia）",
    "ulez": "伦敦超低排放区（ULEZ）",
    "unfocus": "使不聚焦；失去焦点",
    "unretirement": "退休后重返职场",
    "unretirees": "退休后重返职场者",
    "waitlists": "候补名单",
    "wearables": "可穿戴设备",
    "whatsapp": "WhatsApp（即时通讯软件）",
    "wunderlist": "Wunderlist（待办事项应用）",
    "youthsight": "YouthSight（英国调研机构）",
    "confor": "Confor（英国林业协会）",
    "stato": "国家（意大利语，见 Ferrovie dello Stato）",
    # 高频助动词/变形，避免词典首条释义跑偏
    "was": "v. 是（be 的过去式）",
    "are": "v. 是（be 的现在式复数）",
    "am": "v. 是（be 的第一人称单数）",
    "does": "v. 做；助动词（do 的第三人称单数）",
    "based": "a. 以…为基础的；基于",
    "making": "制造；制作（make 的现在分词）",
    "getting": "获得；变得（get 的现在分词）",
}


def candidates(word: str) -> list[str]:
    """粗略还原词形，用于兜底查询。"""
    out: list[str] = []
    if word.endswith("ies"):
        out.append(word[:-3] + "y")
    if word.endswith("ied"):
        out.append(word[:-3] + "y")
    if word.endswith("es"):
        out += [word[:-2], word[:-1]]
    if word.endswith("s") and not word.endswith("ss"):
        out.append(word[:-1])
    if word.endswith("ed"):
        out += [word[:-2], word[:-1]]
    if word.endswith("ing"):
        out += [word[:-3], word[:-3] + "e"]
    if word.endswith("ly"):
        out.append(word[:-2])
    if word.endswith("est"):
        out += [word[:-3], word[:-2]]
    if word.endswith("er"):
        out += [word[:-2], word[:-1]]
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiou":
        out.append(word[:-1])
    return [c for c in out if len(c) > 1]


def simplify(trans: str) -> str:
    """把词典释义压缩成一句简短中文意思。"""
    lines = [ln.strip() for ln in trans.replace("\\n", "\n").split("\n") if ln.strip()]
    if not lines:
        return ""
    general = [ln for ln in lines if not DOMAIN_RE.match(ln)]
    if general:
        line = general[0]
    else:
        # 只有 [计] / [医] / [经] 等专业释义时，去掉标签后使用
        line = DOMAIN_RE.sub("", lines[0]).strip(" ,，")
        if not line:
            return ""
    m = POS_RE.match(line)
    pos, body = (m.group(1), line[m.end():]) if m else ("", line)
    parts = [p.strip() for p in re.split(r"[；;，,]", body) if p.strip()]
    text = "；".join(parts[:3])
    if len(text) > 32:
        cut = text[:32]
        idx = cut.rfind("；")
        text = (cut[:idx] if idx > 8 else cut).rstrip("；") + "…"
    return f"{pos} {text}".strip()


def download_dict() -> None:
    if CACHE.exists():
        return
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    print("首次运行，正在下载 ECDICT 词典（约 63MB）…")
    urllib.request.urlretrieve(DICT_URL, CACHE)
    print("下载完成:", CACHE)


def main() -> None:
    records, years = load_corpus()
    stats = build_stats(records, years)
    words = list(stats["full"].keys())
    word_set = set(words)

    download_dict()

    rows: dict[str, dict] = {}
    with CACHE.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            w = (row["word"] or "").strip().lower()
            if w in word_set:
                rows[w] = row

    # 第一轮：本词条目；同时收集可能需要回退查询的原形/构件
    raw: dict[str, str] = {}
    bases: set[str] = set()
    for w in word_set:
        row = rows.get(w)
        raw[w] = (row.get("translation") or "") if row else ""
        if row:
            m = re.search(r"(?:^|/)0:([a-z'-]+)", row.get("exchange") or "")
            if m:
                bases.add(m.group(1))
        for c in candidates(w):
            bases.add(c)
        if w in IRREGULAR:
            bases.add(IRREGULAR[w])
        if "-" in w:
            head, _, tail = w.rpartition("-")
            bases.update({head, tail})

    need = bases - word_set
    base_rows: dict[str, dict] = {}
    if need:
        with CACHE.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                w = (row["word"] or "").strip().lower()
                if w in need:
                    base_rows[w] = row

    def lookup(w: str) -> str:
        """返回单词的简短中文释义。"""
        if w in SUPPLEMENT:
            return SUPPLEMENT[w]
        trans = raw.get(w, "")
        ex_row = rows.get(w)
        ex_base = None
        if ex_row:
            m = re.search(r"(?:^|/)0:([a-z'-]+)", ex_row.get("exchange") or "")
            ex_base = m.group(1) if m else None

        first_line = trans.split("\n")[0].strip().lower()
        usable = bool(trans) and not META_RE.search(trans.replace("\n", " "))
        # was / were 之类：首条释义是缩写、且明确是某个词的变形时，改查原形
        if usable and ex_base and first_line.startswith("abbr"):
            usable = False
        if usable:
            s = simplify(trans)
            if s:
                return s
        # 变形词 -> 借助原形 / 词形回退
        order = []
        if w in IRREGULAR:
            order.append(IRREGULAR[w])
        if ex_base:
            order.append(ex_base)
        order += candidates(w)
        # 连字符复合词：退而求其次，看后半部分 / 前半部分
        if "-" in w:
            head, _, tail = w.rpartition("-")
            order += [tail, head]
        for c in order:
            if c == w or len(c) < 2:
                continue
            t = raw.get(c) or (base_rows.get(c, {}).get("translation") or "")
            s = simplify(t) if t else ""
            if s:
                return s
        s = simplify(trans) if trans else ""
        return s or "—"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    missing = 0
    proper = 0
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["单词", "中文意思"])
        for w in sorted(words):
            meaning = lookup(w)
            if meaning == "—":
                meaning = "（专有名词）"
                proper += 1
            writer.writerow([w, meaning])

    print(f"单词总数 : {len(words):,}")
    print(f"词典释义 : {len(words) - missing - proper:,}")
    print(f"专有名词 : {proper:,}（标注为「（专有名词）」）")
    print("输出      :", OUT)


if __name__ == "__main__":
    main()
