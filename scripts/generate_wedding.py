#!/usr/bin/env python3
"""从 Notion 数据库生成 wedding/index.html。

环境变量:
  NOTION_TOKEN        Notion internal integration token
  NOTION_DATABASE_ID  数据库 ID

本地测试: python3 scripts/generate_wedding.py --fixture tests/fixtures/notion_rows.json

数据库属性: 姓名(title) 入住人数(number) 抵达(date) 返回(date)
           房型(rich_text，如「8203 湖景标间」) 相邻组(select) 状态(select)
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "wedding", "index.html")
WEEKDAY = "一二三四五六日"  # Monday=0
ROOM_TAG_CLASS = {"新人房": "tag new", "父母房": "tag par", "家庭房": "tag fam", "双床房": "tag"}
ADJ_ORDER = "ABCD"
STAFF_MARK = "老师"  # 姓名含此字样视为工作人员（摄影/摄像/跟妆/管家），不计入宾客人数
# 按「确认人」汇总宾客人数的分组
OWNER_GROUPS = [("臧义程", "程永明", "臧晓军"), ("陈景怡",)]
ADJ_CLASS = {"A": "a", "B": "b", "C": "c", "D": "d"}


def fetch_notion_rows(token, database_id):
    rows, cursor = [], None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        req = urllib.request.Request(
            f"https://api.notion.com/v1/databases/{database_id}/query",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
        rows.extend(data["results"])
        if not data.get("has_more"):
            return rows
        cursor = data["next_cursor"]


def parse_rows(results):
    guests = []
    for page in results:
        p = page["properties"]

        def plain(prop, kind):
            v = p.get(prop) or {}
            if kind == "title":
                return "".join(t["plain_text"] for t in v.get("title") or []).strip()
            if kind == "rich_text":
                return "".join(t["plain_text"] for t in v.get("rich_text") or []).strip()
            if kind == "text":  # rich_text，兼容旧的 select 类型
                if "select" in v:
                    return (v["select"] or {}).get("name") or None
                return "".join(t["plain_text"] for t in v.get("rich_text") or []).strip() or None
            if kind == "number":
                return v.get("number")
            if kind == "select":
                s = v.get("select")
                return s["name"] if s else None
            if kind == "date":
                d = v.get("date")
                return dt.date.fromisoformat(d["start"][:10]) if d and d.get("start") else None
            return None

        name = plain("姓名", "title")
        if not name:
            continue
        guests.append({
            "name": name,
            "people": plain("入住人数", "number") or 0,
            "arrive": plain("抵达", "date"),
            "depart": plain("返回", "date"),
            "room": plain("房型", "text"),
            "room_no": plain("房间号", "text"),
            "group": plain("相邻组", "select"),
            "note": plain("备注", "rich_text"),
            "status": plain("状态", "select"),
            "owner": plain("确认人", "select"),
        })
    return guests


def d_label(d):
    return f"{d.month}/{d.day} {WEEKDAY[d.weekday()]}"


def date_cell(d):
    # 长标签桌面用，短标签（只有日）窄屏用
    return f'<div class="date"><span class="dl">{d_label(d)}</span><span class="ds">{d.day}</span></div>'


def pct(v):
    return f"{v:g}"


def esc(s):
    return html.escape(str(s), quote=False)


def build(guests):
    scheduled = [g for g in guests if g["arrive"] and g["depart"] and g["depart"] > g["arrive"]]
    undated = [g for g in guests if not (g["arrive"] and g["depart"])]
    if not scheduled:
        raise SystemExit("no scheduled guests found; refusing to generate an empty page")

    room_prio = {"新人房": 0, "父母房": 1}
    scheduled.sort(key=lambda g: (
        g["arrive"], -g["depart"].toordinal(), room_prio.get(g["room"], 2), -(g["people"] or 0), g["name"]))

    start = min(g["arrive"] for g in scheduled)
    end = max(g["depart"] for g in scheduled)
    n_nights = (end - start).days
    night_dates = [start + dt.timedelta(days=i) for i in range(n_nights)]

    night_counts = []
    for nd in night_dates:
        night_counts.append(sum(1 for g in scheduled if g["arrive"] <= nd < g["depart"]))
    peak_i = max(range(n_nights), key=lambda i: night_counts[i])
    total_people = sum(int(g["people"] or 0) for g in scheduled)
    guests = [g for g in scheduled if STAFF_MARK not in g["name"]]
    guest_people = sum(int(g["people"] or 0) for g in guests)
    owner_parts = []
    known = set()
    for group in OWNER_GROUPS:
        known.update(group)
        n = sum(int(g["people"] or 0) for g in guests if g["owner"] in group)
        owner_parts.append(f'{" / ".join(group)} 负责 <b>{n}</b> 人')
    unowned = sum(int(g["people"] or 0) for g in guests if g["owner"] not in known)
    if unowned:
        owner_parts.append(f"未填确认人 <b>{unowned}</b> 人")
    headcount = (f"宾客 <b>{guest_people}</b> 人（不含摄影、摄像、跟妆、管家等工作人员 "
                 f"{total_people - guest_people} 人）<br>\n      " + "；".join(owner_parts))

    grid = "<i></i>" * (n_nights - 1) + '<i class="last"></i>'

    nightlabels = "\n".join(
        f"          <em>{nd.month}/{nd.day} 晚<small>周{WEEKDAY[nd.weekday()]}</small></em>"
        for nd in night_dates)

    row_html = []
    for g in scheduled:
        nights = (g["depart"] - g["arrive"]).days
        left = (g["arrive"] - start).days * 100 / n_nights
        width = nights * 100 / n_nights
        adj = f'<i class="adj {ADJ_CLASS[g["group"]]}">{g["group"]}</i>' if g["group"] in ADJ_CLASS else ""
        tag = f'<span class="{ROOM_TAG_CLASS.get(g["room"], "tag")}">{esc(g["room"])}</span>' if g["room"] else ""
        room_no = f'<span class="roomno">{esc(g["room_no"])}</span>' if g["room_no"] else ""
        n1 = " n1" if nights == 1 else ""
        people = int(g["people"] or 0)
        title = html.escape(f'{g["name"]}{" · " + g["room_no"] if g["room_no"] else ""} · {people}人 · {g["arrive"].month}/{g["arrive"].day} 入住，'
                    f'{g["depart"].month}/{g["depart"].day} 退房，{nights}晚')
        row_html.append(
            f'    <div class="row body-row"><div><span class="name">{esc(g["name"])}</span>{room_no}{adj}</div>'
            f'<div class="num">{people}</div>'
            f'{date_cell(g["arrive"])}{date_cell(g["depart"])}'
            f'<div class="note">{tag}</div>'
            f'<div class="tl"><div class="tl-grid">{grid}</div>'
            f'<div class="bar{n1}" style="left:{pct(left)}%;width:{pct(width)}%" title="{title}">'
            f'<em>{nights}晚</em></div></div></div>')

    totals = "\n".join(
        f"          <b>{c}<small>{nd.month}/{nd.day} 晚</small></b>"
        for nd, c in zip(night_dates, night_counts))

    adj_lines = []
    for letter in ADJ_ORDER:
        members = [g["name"] for g in scheduled if g["group"] == letter]
        if members:
            adj_lines.append(
                f'      <span class="adj-item"><i class="adj {ADJ_CLASS[letter]}">{letter}</i>'
                + esc(" / ".join(members)) + "</span>")
    adj_html = "<br>\n".join(adj_lines)

    if undated:
        pending = "、".join(f'<b>{esc(g["name"])}</b>（{int(g["people"] or 0)} 人）' for g in undated) + "，确认后补入。"
    else:
        pending = "无。"

    date_range = (f"{start.year} 年 {start.month} 月 {start.day} 日 — "
                  f"{end.month} 月 {end.day} 日")
    peak_nd = night_dates[peak_i]

    return TEMPLATE.format(
        n_nights=n_nights,
        date_range=date_range,
        n_groups=len(scheduled),
        peak_count=night_counts[peak_i],
        peak_label=f"{peak_nd.month}/{peak_nd.day}",
        total_people=total_people,
        headcount=headcount,
        grid=grid,
        nightlabels=nightlabels,
        rows="\n".join(row_html),
        totals=totals,
        adj_lines=adj_html,
        pending=pending,
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>婚礼来宾住宿排期</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap">
<style>
  /* 单主题设计：纸面预订单，所有颜色显式指定。本文件由 scripts/generate_wedding.py 从 Notion 生成，勿手改 */
  :root {{
    --paper: #FCFAF6;
    --card: #FFFFFF;
    --ink: #2E2723;
    --muted: #8C7F74;
    --faint: #B8AB9E;
    --line: #E9E1D5;
    --line-strong: #D8CCBB;
    --red: #A62B24;
    --red-deep: #7E1F1A;
    --red-wash: #F7ECE8;
    --gold: #9C7A3C;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    background: var(--paper);
    color: var(--ink);
    font-family: "Noto Sans SC", "PingFang SC", "Hiragino Sans GB", sans-serif;
    font-size: 14px;
    line-height: 1.5;
    margin: 0;
    padding: 40px 24px 56px;
  }}
  .sheet {{ max-width: 1000px; margin: 0 auto; }}

  header {{ display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 8px 24px; border-bottom: 3px double var(--red); padding-bottom: 16px; }}
  h1 {{
    font-family: "Noto Serif SC", "Songti SC", serif;
    font-size: 30px; font-weight: 700; margin: 0; letter-spacing: 2px;
    color: var(--red-deep); text-wrap: balance;
  }}
  h1 .xi {{ color: var(--gold); font-size: 22px; margin-right: 10px; }}
  .daterange {{ font-size: 15px; color: var(--muted); letter-spacing: 1px; }}
  .daterange strong {{ color: var(--ink); font-weight: 500; }}

  .stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0 28px; }}
  .stat {{
    background: var(--card); border: 1px solid var(--line); border-radius: 6px;
    padding: 10px 18px; min-width: 132px;
  }}
  .stat b {{ display: block; font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--red-deep); }}
  .stat span {{ font-size: 12px; color: var(--muted); letter-spacing: .08em; }}
  .stat small {{ font-size: 12px; color: var(--faint); font-weight: 400; }}

  .scroll {{ overflow-x: auto; }}
  .chart {{ min-width: 1036px; background: var(--card); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}

  .row {{
    display: grid;
    grid-template-columns: 240px 52px 78px 78px 120px 1fr;
    align-items: stretch;
  }}
  .row > div {{ padding: 0 10px; display: flex; align-items: center; min-height: 34px; }}
  .body-row {{ border-top: 1px solid var(--line); }}
  .body-row:hover {{ background: var(--red-wash); }}

  .head {{ background: var(--paper); border-bottom: 1px solid var(--line-strong); }}
  .head > div {{ font-size: 12px; font-weight: 700; color: var(--muted); letter-spacing: .12em; min-height: 30px; }}
  .head .tl {{ padding: 0; }}

  .row > div:first-child {{ min-width: 0; }}
  .name {{ min-width: 0; font-weight: 500; line-height: 1.35; padding: 7px 0; overflow-wrap: anywhere; }}
  .roomno {{ flex: none; margin-left: 6px; font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .num {{ justify-content: center; font-variant-numeric: tabular-nums; color: var(--ink); }}
  .num.zero {{ color: var(--faint); }}
  .date {{ font-variant-numeric: tabular-nums; color: var(--muted); font-size: 13px; white-space: nowrap; }}

  /* 时间轴：每列 = 一晚 */
  .tl {{ position: relative; padding: 0 !important; }}
  .tl-grid {{ position: absolute; inset: 0; display: grid; grid-template-columns: repeat({n_nights}, 1fr); }}
  .tl-grid i {{ border-left: 1px solid var(--line); }}
  .tl-grid i:nth-child(even) {{ background: rgba(233, 225, 213, 0.22); }}
  .tl-grid i.last {{ border-right: 1px solid var(--line); }}

  .tag {{
    border: 1px solid #E5C9C2; border-radius: 3px; padding: 1px 6px;
    font-size: 11px; color: var(--red-deep); background: var(--red-wash);
  }}
  .tag.fam {{ color: var(--gold); background: #F6F0E3; border-color: #E0D2B4; }}
  .tag.new {{ color: #FCF6EF; background: var(--red); border-color: var(--red-deep); }}
  .tag.par {{ color: #FCF6EF; background: var(--gold); border-color: #7E6230; }}

  /* 相邻房分组圆点 */
  .adj {{
    font-style: normal; flex: none; margin-left: 6px;
    width: 16px; height: 16px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700; color: #FFFFFF;
  }}
  .adj.a {{ background: #3E6B9E; }}
  .adj.b {{ background: #4A7C59; }}
  .adj.c {{ background: #7C5CA8; }}
  .adj.d {{ background: #B5762A; }}

  /* 列头：每列 = 一晚，标签居中在列内 */
  .nightlabels {{ position: absolute; inset: 0; display: grid; grid-template-columns: repeat({n_nights}, 1fr); }}
  .nightlabels em {{
    font-style: normal; display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; color: var(--ink); white-space: nowrap;
  }}
  .nightlabels em small {{ color: var(--faint); font-weight: 400; margin-left: 3px; }}

  .bar {{
    position: absolute; top: 50%; transform: translateY(-50%);
    height: 18px; border-radius: 4px;
    background: var(--red);
    display: flex; align-items: center; justify-content: flex-end;
    padding-right: 6px;
    box-shadow: inset 0 0 0 1px rgba(126, 31, 26, 0.35);
  }}
  .bar em {{ font-style: normal; font-size: 11px; font-weight: 500; color: #FCF6EF; letter-spacing: .05em; white-space: nowrap; }}
  .bar.n1 {{ justify-content: center; padding-right: 0; }}

  /* 每晚在住组数汇总 */
  .totals {{ border-top: 2px solid var(--line-strong); background: var(--paper); }}
  .totals .label {{ grid-column: 1 / 6; justify-content: flex-end; font-size: 12px; font-weight: 700; color: var(--muted); letter-spacing: .12em; }}
  .totals .tl {{ min-height: 44px; }}
  .night-cells {{ position: absolute; inset: 0; display: grid; grid-template-columns: repeat({n_nights}, 1fr); }}
  .night-cells b {{
    border-left: 1px solid var(--line); display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 1px;
    font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--red-deep);
  }}
  .night-cells b:last-child {{ border-right: 1px solid var(--line); }}
  .night-cells b small {{ font-size: 10px; font-weight: 400; color: var(--faint); letter-spacing: .05em; }}

  .legend {{ margin-top: 18px; display: grid; grid-template-columns: 5.5em 1fr; gap: 6px 14px; font-size: 13px; color: var(--muted); max-width: 860px; }}
  .legend dt {{ margin: 0; font-weight: 700; font-size: 12px; color: var(--gold); letter-spacing: .1em; line-height: 1.7; }}
  .legend dd {{ margin: 0; line-height: 1.7; }}
  .legend b {{ color: var(--ink); font-weight: 500; }}
  .legend .adj {{ width: 15px; height: 15px; margin: 0 4px 0 0; vertical-align: -2px; }}
  .legend .adj-item {{ white-space: nowrap; margin-right: 14px; }}

  .pagefoot {{ margin-top: 22px; padding-top: 12px; border-top: 1px solid var(--line); font-size: 12px; color: var(--faint); }}
  .pagefoot a.syncbtn {{ color: var(--red-deep); text-decoration: none; border: 1px solid var(--line-strong); border-radius: 4px; padding: 2px 8px; margin-left: 6px; background: var(--card); }}
  .pagefoot a.syncbtn:hover {{ background: var(--red-wash); }}

  .ds {{ display: none; }}

  /* 窄屏：不横向滚动；每组第一行是文字信息，第二行是整宽时间轴，日期只显示「日」 */
  @media (max-width: 760px) {{
    body {{ padding: 24px 16px 40px; }}
    h1 {{ font-size: 24px; }}
    .stats {{ gap: 8px; margin: 16px 0 20px; }}
    .stat {{ flex: 1 1 0; min-width: 0; padding: 8px 10px; }}
    .stat b {{ font-size: 20px; }}
    .scroll {{ overflow: visible; }}
    .chart {{ min-width: 0; }}
    .dl {{ display: none; }}
    .ds {{ display: inline; }}
    .row {{ grid-template-columns: minmax(0, 1fr) 24px 26px 26px 98px; }}
    .row > div {{ padding: 0 3px; }}
    .row > div:first-child {{ padding-left: 10px; }}
    .row > div:nth-child(5) {{ padding-right: 8px; }}
    .date {{ justify-content: center; font-size: 14px; color: var(--ink); }}
    .head > div {{ letter-spacing: 0; justify-content: center; }}
    .head > div:first-child {{ justify-content: flex-start; }}
    .tl {{ grid-column: 1 / -1; min-height: 22px !important; margin: 0 8px 6px 10px; }}
    .head .tl {{ min-height: 26px !important; margin-bottom: 0; }}
    .nightlabels em {{ font-size: 11px; }}
    .bar {{ height: 14px; }}
    .bar em {{ font-size: 10px; }}
    .tag {{ display: inline-block; text-align: center; line-height: 1.3; padding: 2px 5px; }}
    .pagefoot a.syncbtn {{ white-space: nowrap; display: inline-block; margin: 6px 0 0; }}
    .totals .label {{ grid-column: 1 / -1; justify-content: flex-start; padding-top: 6px; }}
    .totals .tl {{ min-height: 40px !important; }}
    .legend {{ grid-template-columns: 1fr; gap: 2px; }}
    .legend dd {{ margin-bottom: 8px; }}
    .legend .adj-item {{ display: block; white-space: normal; margin-right: 0; }}
  }}
  @media (max-width: 400px) {{
    .name {{ font-size: 13px; }}
    .row {{ grid-template-columns: minmax(0, 1fr) 22px 24px 24px 94px; }}
    .adj {{ margin-left: 4px; }}
    .stat span {{ font-size: 11px; letter-spacing: 0; }}
  }}

  @media print {{
    body {{ padding: 0; background: #FFFFFF; }}
    .scroll {{ overflow: visible; }}
    .chart {{ border-color: var(--line-strong); }}
    .stat, .chart {{ break-inside: avoid; }}
    .pagefoot a.syncbtn {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="sheet">
  <header>
    <h1><span class="xi">囍</span>婚礼来宾住宿排期</h1>
    <div class="daterange">宁波 · <strong>{date_range}</strong></div>
  </header>

  <div class="stats">
    <div class="stat"><b>{n_groups} <small>组</small></b><span>已排入住</span></div>
    <div class="stat"><b>{peak_count} <small>组</small></b><span>峰值夜 · {peak_label}</span></div>
    <div class="stat"><b>{total_people} <small>人</small></b><span>入住总人数</span></div>
  </div>

  <div class="scroll">
  <div class="chart">
    <div class="row head">
      <div>姓名</div><div style="justify-content:center"><span class="dl">入住</span><span class="ds">人</span></div><div><span class="dl">抵达</span><span class="ds">抵</span></div><div><span class="dl">返回</span><span class="ds">返</span></div><div><span class="dl">备注</span><span class="ds">房间</span></div>
      <div class="tl">
        <div class="tl-grid">{grid}</div>
        <div class="nightlabels">
{nightlabels}
        </div>
      </div>
    </div>

{rows}

    <div class="row totals">
      <div class="label">每晚在住组数</div>
      <div class="tl">
        <div class="night-cells">
{totals}
        </div>
      </div>
    </div>
  </div>
  </div>

  <dl class="legend">
    <dt>人数</dt>
    <dd>{headcount}</dd>
    <dt>读法</dt>
    <dd>时间轴每列代表一晚住宿：红条盖到哪列，就住哪晚（如 10/5 抵达、10/6 返回＝只住「10/5 晚」一列）。「入住」为每组入住人数。</dd>
    <dt>房型</dt>
    <dd>见备注列；未标注的大床、双床均可。</dd>
    <dt>相邻房</dt>
    <dd>
      姓名后同字母圆点＝房间尽量相邻：<br>
{adj_lines}
    </dd>
    <dt>日期待定</dt>
    <dd>{pending}</dd>
  </dl>

  <p class="pagefoot">数据更新于 __UPDATED_AT__（北京时间）· 数据源 Notion，每 30 分钟自动同步<a class="syncbtn" href="https://github.com/Lomolanisgo/lomolanisgo.github.io/actions/workflows/update-wedding.yml" target="_blank" rel="noopener">🔄 立即同步</a></p>
</div>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="本地测试：Notion query results 的 JSON 文件")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    if args.fixture:
        with open(args.fixture) as f:
            results = json.load(f)
    else:
        token = os.environ.get("NOTION_TOKEN")
        database_id = os.environ.get("NOTION_DATABASE_ID")
        if not token or not database_id:
            print("NOTION_TOKEN / NOTION_DATABASE_ID not set", file=sys.stderr)
            return 2
        results = fetch_notion_rows(token, database_id)

    page = build(parse_rows(results))
    out = os.path.abspath(args.out)

    # 时间戳含义为「数据最后更新时间」：数据没变就保留旧文件（含旧时间戳），
    # 这样 Action 的 git diff 仍为空，不会每 30 分钟白提交一次。
    ts_re = re.compile(r"数据更新于 \d{4}-\d{2}-\d{2} \d{2}:\d{2}")
    if os.path.exists(out):
        with open(out) as f:
            existing = f.read()
        if ts_re.sub("数据更新于 __UPDATED_AT__", existing) == page:
            print("no data change; keeping existing file")
            return 0
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    page = page.replace("__UPDATED_AT__", now)
    with open(out, "w") as f:
        f.write(page)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
