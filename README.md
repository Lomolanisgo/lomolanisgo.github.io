# 韩语分级学习词汇数据库

本项目同时包含独立学习网站 **`/korean/`**。前端开发、搜索筛选、学习记录、构建和现有 GitHub Pages 部署说明见 [korean-app/README.md](korean-app/README.md)。快速启动：`cd korean-app && npm ci && npm run dev`。数据库说明与 Python 流程如下。

完整收录国立国语院 **2003 年《한국어 학습용 어휘 목록》5,965 条**。这是指定版本的完整词表，不是韩国语基础词典全部词条，也不是全部年代的官方教育词汇合集。原表 A/B/C 分别为 1/2/3 阶段；本项目以初级/中级/高级显示，**不换算为 TOPIK 1–6 级**。

## 运行

Python 3.10+：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -p test_vocabulary.py
```

默认读取随项目保存的原始快照，核对 SHA-256 后离线重建所有输出。不需要词典 API 密钥。依赖安装需要网络。

```bash
# 显式联网刷新快照；来源格式或完整性检查失败会报错
python main.py --download
# 保持第三方补充字段为空，单独导出纯官方版本
python main.py --official-only --output-dir outputs/official-only
# 将全部输出写到另一目录
python main.py --output-dir outputs/rebuilt
```

`--download` 会更新原始快照和 manifest；要复现本次结果，请保留当前 `data/raw/`。刷新后应重新检查差异报告。默认流程逻辑与数据可复现；XLSX ZIP 时间戳及数据库文件布局不承诺逐字节一致。脚本不会创建词汇或调用模型生成释义。

## 数据来源及核验范围

1. 官方发布页：https://www.korean.go.kr/front/etcData/etcDataView.do?etc_seq=70&mn_id=46&pageIndex=1
   - 官方 TXT 原件以 CP949 解码，含频次排名、带同音词编号的词头、词性、原语/说明、A/B/C。
   - 发布页载明 KOGL 第 1 类型（署名）利用条件。归属：국립국어원，2003《한국어 학습용 어휘 목록》。不是现代口语或综艺频率表。
2. 第三方：https://topikvocab.foldalpha.com/download/
   - 中文和英文 CSV 各 5,965 行。按“无编号词头、官方词性、频次排名、分级”四元键逐条核对，两份均完全覆盖官方表，键唯一，无缺项、多项。
   - 第三方未提供官方同音编号；利用经检查唯一的四元键关联，绝不按词头直接去重。
   - 中英文释义、韩语例句及其中文翻译为该站自行提供，**不属于官方译文，未逐句验证语义或教学质量**。网站许可这些补充内容用于学习；不要将官方 KOGL 许可误套于全部第三方内容。
   - 汉字以官方为准；差异逐条列在 `validation_report.json`。比较时允许 Unicode 兼容字形等价，但输出不简化汉字、不改写原字形。官方数字 HTML 实体会解码，例如 `&#29518;` → `獎`。
3. 韩国语基础词典：https://krdict.korean.go.kr/ ，下载入口：https://krdict.korean.go.kr/download/downloadPopup
   - 本次直接下载被网站防火墙阻挡，未取得可核验的词条原件。因此没有使用该词典补齐发音、词源或官方释义；标准发音全部留空。代码不会声称已经接入此词典。

下载地址、原件大小和 SHA-256 在 `data/raw/manifest.json`。`provenance.json` 以及 SQLite 的 provenance 表保留每条的官方原词头、同音编号、原始说明、频次、分类依据和第三方行号。

## 字段

| 字段 | 说明 |
|---|---|
| ID | 根据官方带编号词头＋词性生成稳定唯一 ID；不同词性亦不合并 |
| Korean | 移除官方词头末尾的同音编号；其余原样保留，动词/形容词不变形 |
| Hanja | 官方原语中的汉字成分，保留传统及兼容/异体字；混合词仅列汉字部分，不代表整词完全对应 |
| Chinese | 第三方简体中文释义，原样保留 |
| English | 第三方英文释义 |
| POS | 官方词性缩写的中文标签；“보”保留为辅助谓词，不臆分辅助动词/形容词 |
| Level | 官方 A/B/C 及阶段号，附初/中/高级显示标签 |
| Word_Type | 从官方原语明确标注推导的汉字词/外来词/混合词；不能确认时为空 |
| Pronunciation | 本次全部空，不由拼写猜读音 |
| Example | 第三方中文版本附带的韩语例句 |
| Example_CN | 与上述同一例句对应的第三方中文翻译 |
| Source | 官方出处 URL，以及使用补充内容时的第三方 URL 和非官方标记 |

缺失值在 CSV/JSON/SQLite 中均为空字符串，在 Excel 中为空单元格。汉字缺失不一定是数据错误，固有词和纯外来词本来就可能没有对应汉字。

词源规则：原语全为汉字 → 汉字词；汉字与拉丁字母或 `-` 固有成分占位符混合 → 混合词（含汉字词根＋하다 等派生词）；原语明确为拉丁字母（允许语言前缀）→ 外来词。**无原语不能推出固有词**。因此固有词未确认，数量 0 只是已确认数量；所有分类是透明规则的推导结果，不是官方独立词源字段。原语完整形式保存在 provenance 中。

## 输出

- `vocabulary.csv`：UTF-8 BOM，方便 Excel 打开。
- `vocabulary.xlsx`：5,965 行词汇，12 字段筛选表，冻结表头与 ID/词头，附说明与统计。
- `vocabulary.json`：12 字段对象数组。
- `vocabulary.db`：SQLite vocabulary、provenance 表及词头/等级词源索引。
- `anki.tsv`：5,965 条，12 数据字段＋标签列，首字段为唯一 ID 防止同形词误合并。
- `quality_report.json`：总量、分级、词性、分类比例、重复和缺失统计。
- `validation_report.json`：两份第三方表的覆盖核验及汉字差异。
- `provenance.json`：逐条追溯信息。

## Anki 导入

创建自定义笔记类型，依次添加与数据库相同的 12 个字段（ID 必须为第一字段）。导入 `anki.tsv`，分隔符为 Tab、允许 HTML，将第 13 列映射为 Tags。文件带导入指令，但仍需选中该自定义笔记类型。

正面模板（词性、汉字辅助区分同形词）：

```html
{{Korean}}<br>{{POS}} · {{Hanja}}
```

背面模板：

```html
{{FrontSide}}<hr id="answer">
{{Chinese}}<br>{{English}}<br>{{Pronunciation}}
<hr>{{Example}}<br>{{Example_CN}}<br>{{Level}}
<hr><small>{{Source}}</small>
```

## 本次数据质量

总数 5,965；初级 982、中级 2,111、高级 2,872。重复 ID 和完全重复行均 0。同词头造成的额外行有 422 条，保留这些同音/同形/多词性条目。

| 词源分类 | 已确认数量 | 全表占比 |
|---|---:|---:|
| 汉字词 | 2,464 | 41.3076% |
| 外来词 | 245 | 4.1073% |
| 混合词 | 843 | 14.1324% |
| 固有词 | 0（尚未确认） | 0%（非实际比例） |
| 未确认 | 2,413 | 40.4526% |

含汉字成分共 3,307 条。缺失：Hanja 2,658、Word_Type 2,413、Pronunciation 5,965；其余请求字段均非空。非空不等于已经通过翻译准确性审核。

词性：名词 3,404；动词 1,345；副词 393；形容词 376；辅助谓词 33；依存名词 130；冠形词 69；专有名词 63；不可分析 14；代词 47；数词 47；感叹词 44。更新数据后的实际统计以程序输出和 quality_report 为准。

## 面向汉语母语学习者

可先筛选 A/B 级且 Hanja 非空的记录，按汉字词根对照记忆，再学习相关动词/形容词及搭配；这只是学习顺序建议，不表示覆盖 TOPIK 4 级要求。汉韩同形字词可能意义不同，请结合例句并用基础词典人工复核第三方译文。

该 2003 年词表不是完整语法、助词或词尾数据库，没有额外造出词尾记录。综艺口语、省略、缩略形式、流行语也不保证覆盖。应配合真实节目字幕及正规语法材料学习；不要把本表书面语频率当作综艺词频。

SQLite 示例：

```sql
SELECT Korean, Hanja, Chinese, POS, Level
FROM vocabulary
WHERE Hanja <> '' AND Level IN ('初级（A／1阶段）', '中级（B／2阶段）')
ORDER BY Hanja, Korean;
```
