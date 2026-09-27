"""运行: python3 -m unittest discover -s tests"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import unittest

_spec = importlib.util.spec_from_file_location(
    "generate_wedding", os.path.join(os.path.dirname(__file__), "..", "scripts", "generate_wedding.py"))
gw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gw)


def page(room=None, room_no=None, name="张三", owner=None, people=2, status="已确定"):
    props = {
        "姓名": {"title": [{"plain_text": name}]},
        "入住人数": {"number": people},
        "抵达": {"date": {"start": "2026-10-03"}},
        "返回": {"date": {"start": "2026-10-05"}},
        "相邻组": {"select": None},
        "备注": {"rich_text": []},
        "状态": {"select": {"name": status}},
        "确认人": {"select": {"name": owner} if owner else None},
    }
    if room is not None:
        props["房型"] = room
    if room_no is not None:
        props["房间号"] = room_no
    return {"properties": props}


def text(s):
    return {"rich_text": [{"plain_text": s}] if s else []}


class ParseRowsTest(unittest.TestCase):
    def test_room_type_as_text(self):
        g = gw.parse_rows([page(room=text("大床房"))])[0]
        self.assertEqual(g["room"], "大床房")

    def test_room_type_legacy_select_still_parsed(self):
        g = gw.parse_rows([page(room={"select": {"name": "新人房"}})])[0]
        self.assertEqual(g["room"], "新人房")

    def test_empty_room_type_is_none(self):
        g = gw.parse_rows([page(room=text(""))])[0]
        self.assertIsNone(g["room"])

    def test_room_number(self):
        g = gw.parse_rows([page(room_no=text(" A-201 "))])[0]
        self.assertEqual(g["room_no"], "A-201")

    def test_missing_room_number_column(self):
        g = gw.parse_rows([page()])[0]
        self.assertIsNone(g["room_no"])


class BuildTest(unittest.TestCase):
    def test_room_number_next_to_name(self):
        html = gw.build(gw.parse_rows([page(room_no=text("201"))]))
        self.assertIn('<span class="name">张三</span><span class="roomno">201</span>', html)

    def test_no_room_number_span_when_empty(self):
        html = gw.build(gw.parse_rows([page()]))
        self.assertNotIn('<span class="roomno">', html)

    def test_room_number_escaped(self):
        html = gw.build(gw.parse_rows([page(room_no=text("<b>1</b>"))]))
        self.assertIn('<span class="roomno">&lt;b&gt;1&lt;/b&gt;</span>', html)

    def test_known_room_type_keeps_colored_tag(self):
        html = gw.build(gw.parse_rows([page(room=text("新人房"))]))
        self.assertIn('<span class="tag new">新人房</span>', html)

    def test_free_text_room_type_gets_plain_tag(self):
        html = gw.build(gw.parse_rows([page(room=text("大床房"))]))
        self.assertIn('<span class="tag">大床房</span>', html)

    def test_long_name_not_truncated(self):
        html = gw.build(gw.parse_rows([page(name="张博（伴）王永恒 & 杨子丰")]))
        name_css = next(l for l in html.splitlines() if l.strip().startswith(".name {"))
        self.assertNotIn("ellipsis", name_css)
        self.assertNotIn("nowrap", name_css)

    def test_dates_have_long_and_short_labels(self):
        html = gw.build(gw.parse_rows([page()]))
        self.assertIn('<div class="date"><span class="dl">10/3 六</span><span class="ds">3</span></div>', html)
        self.assertIn('<div class="date"><span class="dl">10/5 一</span><span class="ds">5</span></div>', html)

    def test_mobile_media_query_present(self):
        html = gw.build(gw.parse_rows([page()]))
        self.assertIn("@media (max-width: 760px)", html)

    def test_headcount_legend_by_owner(self):
        rows = [page(name="臧义程 & 陈景怡", owner="臧义程"),
                page(name="张博（伴）王永恒 & 杨子丰", owner="臧义程", people=3),
                page(name="周恒（伴）", owner="臧义程", people=1),
                page(name="李四", owner="程永明"), page(name="王五", owner="臧晓军"),
                page(name="赵六", owner="陈景怡"), page(name="摄影老师x2", owner="陈景怡")]
        html = gw.build(gw.parse_rows(rows))
        self.assertIn("<b>14 <small>人</small></b><span>入住总人数</span>", html)
        self.assertIn("宾客 <b>12</b> 人（不含摄影、摄像、跟妆、管家等工作人员 2 人）", html)
        self.assertIn("新人 <b>2</b> 人；伴郎 <b>2</b> 人", html)
        self.assertIn("臧义程 / 程永明 / 臧晓军 负责 <b>6</b> 人", html)
        self.assertIn("陈景怡 负责 <b>2</b> 人", html)
        self.assertNotIn("未填确认人", html)

    def test_star_marks_groomsman(self):
        rows = [page(name="张博* & 王永恒 & 杨子丰", owner="臧义程", people=3),
                page(name="周恒*", owner="臧义程", people=1)]
        html = gw.build(gw.parse_rows(rows))
        self.assertIn("伴郎 <b>2</b> 人", html)
        self.assertIn("臧义程 / 程永明 / 臧晓军 负责 <b>2</b> 人", html)

    def test_pending_rows_not_counted(self):
        rows = [page(name="张三", owner="臧义程"),
                page(name="待定人", owner="臧义程", status="待定")]
        html = gw.build(gw.parse_rows(rows))
        self.assertIn("<b>2 <small>人</small></b><span>入住总人数</span>", html)
        self.assertIn("臧义程 / 程永明 / 臧晓军 负责 <b>2</b> 人", html)

    def test_headcount_legend_reports_missing_owner(self):
        html = gw.build(gw.parse_rows([page(name="张三")]))
        self.assertIn("未填确认人 <b>2</b> 人", html)


    def test_chart_fits_sheet_on_desktop(self):
        html = gw.build(gw.parse_rows([page()]))
        sheet = int(re.search(r"\.sheet \{ max-width: (\d+)px", html).group(1))
        chart = int(re.search(r"\.chart \{ min-width: (\d+)px", html).group(1))
        self.assertLessEqual(chart, sheet)


class SortTest(unittest.TestCase):
    def test_rows_carry_sort_keys(self):
        rows = [page(name="张三", room=text("8203 湖景标间")), page(name="李四")]
        rows[0]["properties"]["相邻组"] = {"select": {"name": "B"}}
        html = gw.build(gw.parse_rows(rows))
        self.assertIn('data-arrive="2026-10-03" data-room="8203" data-group="B"', html)
        self.assertIn('data-arrive="2026-10-03" data-room="" data-group=""', html)

    def test_sorter_controls_present(self):
        html = gw.build(gw.parse_rows([page()]))
        self.assertIn('id="sorter"', html)
        for key in ("arrive", "room", "group"):
            self.assertIn(f'data-key="{key}"', html)

    def test_mobile_hides_people_and_date_columns(self):
        html = gw.build(gw.parse_rows([page()]))
        mobile = html[html.index("@media (max-width: 760px)"):]
        self.assertIn(".num, .date,", mobile[:mobile.index("@media print")])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_sort_order_logic(self):
        js = gw.SORT_JS
        items = [
            {"idx": 0, "arrive": "2026-10-03", "room": "8303", "group": ""},
            {"idx": 1, "arrive": "2026-10-03", "room": "8102", "group": "B"},
            {"idx": 2, "arrive": "2026-10-04", "room": "", "group": "A"},
            {"idx": 3, "arrive": "2026-10-04", "room": "8201", "group": "B"},
        ]
        cases = {
            ("arrive", ""): [0, 1, 2, 3],
            ("room", ""): [1, 3, 0, 2],          # 无房号排最后
            ("group", ""): [2, 1, 3, 0],         # 无分组排最后
            ("group", "room"): [2, 1, 3, 0],
            ("group", "arrive"): [2, 1, 3, 0],
            ("arrive", "room"): [1, 0, 3, 2],
            ("arrive", "group"): [1, 0, 2, 3],
        }
        script = js + "\nconst items=" + json.dumps(items) + ";\nconst cases=" + json.dumps(
            [list(k) for k in cases]) + ";\nconsole.log(JSON.stringify(cases.map(c => " \
            "module.exports.order(items, c[0], c[1]).map(x => x.idx))));"
        out = subprocess.run(["node", "-e", "var module={exports:{}};" + script],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), list(cases.values()))


if __name__ == "__main__":
    unittest.main()
