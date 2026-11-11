# 考研英语（二）十年真题词频统计（2017—2026）

把 `10年真题/` 下 10 套考研英语（二）试卷当作一个大文本，统计其中每个单词的出现次数，按词频从高到低排序，输出为 CSV、Excel 与可视化报告。

## 数据概览

| 指标 | 数值 |
| --- | --- |
| 试卷数量 | 10 套（2017—2026） |
| 总词数（含题干、选项、指令） | 34,593 |
| 不同词形总数 | 5,515 |
| 文章正文词数 | 25,494 |
| 不同实词数 | 4,647 |
| 只出现 1 次的单词 | 2,550 |
| 覆盖 50% 正文所需单词 | 131 |
| 覆盖 80% 正文所需单词 | 1,153 |
| 覆盖 90% 正文所需单词 | 2,267 |
| 覆盖 95% 正文所需单词 | 3,534 |

## 三种统计口径

| 统计范围 | 说明 |
| --- | --- |
| 全量词频 | 正文 + 题干 + 选项 + 考试指令，即试卷里出现的所有英文单词 |
| 正文词频 | 只统计文章正文（完形文章、阅读 Text 1—4、新题型、翻译原文） |
| 实词词频 | 在正文基础上剔除 the / a / of / is 等高频功能词，最接近需要背诵的核心词汇 |

## 交付物

| 文件 | 说明 |
| --- | --- |
| `output/词频简表.xlsx` | 精简版：只有「单词」「中文意思」「词频」三列，5,515 行，按词频降序 |
| `output/考研英语二2017-2026词频总表.xlsx` | 主表：统计说明、全量词频、正文词频、实词词频、分年份概览、分题型概览 |
| `output/词频总表_全量.csv` | 全量词频表（含各年份次数、出现年份数、功能词/实词标记） |
| `output/词频总表_正文.csv` | 正文词频表 |
| `output/词频总表_实词.csv` | 实词词频表（已重新连续排名） |
| `output/词频分析报告.html` | 可视化报告：词频排行、背词覆盖效率、分年份/分题型词量 |
| `data/word_meanings.csv` | 5,515 个单词的中文释义对照表（释义来源：ECDICT 英汉词典） |

## 高频实词 Top 20（正文口径）

| 排名 | 单词 | 词频 | 出现年份数 |
| --- | --- | --- | --- |
| 1 | people | 88 | 10 |
| 2 | time | 79 | 10 |
| 3 | says | 78 | 10 |
| 4 | new | 62 | 9 |
| 5 | need | 53 | 10 |
| 6 | work | 53 | 10 |
| 7 | help | 50 | 10 |
| 8 | even | 47 | 9 |
| 9 | like | 46 | 10 |
| 10 | make | 45 | 10 |
| 11 | health | 44 | 7 |
| 12 | year | 42 | 10 |
| 13 | said | 39 | 7 |
| 14 | high | 38 | 9 |
| 15 | feel | 37 | 10 |
| 16 | social | 36 | 9 |
| 17 | change | 34 | 10 |
| 18 | good | 34 | 10 |
| 19 | get | 33 | 10 |
| 20 | students | 32 | 7 |

## 中文释义说明

- 释义取自开源词典 [ECDICT](https://github.com/skywind3000/ECDICT)（MIT License），每个词只保留前 1—3 个常用义项，并保留 `n.` `v.` `a.` 等词性缩写；
- 变形词（`says`、`students`、`went`）优先给出其原形的意思；
- 词典未收录的专有名词（人名、公司名、地名等）统一标注为「（专有名词）」，共 47 个；
- 词典中确实缺少的真题派生词与新词（如 `reskilling`、`prosociality`、`parkrun`、`tipflation`）由 `scripts/build_word_meanings.py` 内的 `SUPPLEMENT` 表人工补齐。

## 分词与统计规则

- 只统计由英文字母构成的单词，忽略数字、标点、选项标号（`[A]`）和 Markdown 标记；
- 统一转为小写，因此 `The` 与 `the` 合并计为一个词；
- 所有格归到词根：`Parkrun's` → `parkrun`，`kids'` → `kids`；
- 连字符复合词拆成两个单词分别计数：`carbon-absorbing` → `carbon` + `absorbing`，`well-paid` → `well` + `paid`；
- 缩写保留整体：`don't` 计为一个词；
- 不区分词形：`work` / `works` / `working` / `worked` 分别计数（词频统计按原形，不做词形还原）；
- 单字母不计入（`a`、`I` 以及选项字母等）；
- 每张表的「占比」均以该表统计范围的总词数为分母。

## 目录结构

```
27-en-words-exam/
├── 10年真题/                          # 原始试卷（2017.md — 2026.md）
├── scripts/build_word_frequency.py    # 统计脚本（解析、分词、导出）
├── scripts/build_word_meanings.py     # 释义脚本（下载 ECDICT、生成中文意思）
├── data/word_meanings.csv             # 单词 → 中文意思 对照表
└── output/                            # 生成的词频表与报告
```

## 复现

```bash
python scripts/build_word_meanings.py   # 先生成 data/word_meanings.csv（首次会下载词典）
python scripts/build_word_frequency.py  # 再生成 output/ 下的全部表格与报告
```

依赖：Python 3.9+、openpyxl（仅用于导出 Excel）。`build_word_frequency.py` 若检测到 `data/word_meanings.csv` 会为简表补上「中文意思」列，否则只输出「单词 + 词频」两列。
