"""运行: python3 -m unittest discover -s tests"""
import importlib.util
import os
import unittest

_spec = importlib.util.spec_from_file_location(
    "generate_wedding", os.path.join(os.path.dirname(__file__), "..", "scripts", "generate_wedding.py"))
gw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gw)


def page(room=None, room_no=None, name="张三"):
    props = {
        "姓名": {"title": [{"plain_text": name}]},
        "入住人数": {"number": 2},
        "抵达": {"date": {"start": "2026-10-03"}},
        "返回": {"date": {"start": "2026-10-05"}},
        "相邻组": {"select": None},
        "备注": {"rich_text": []},
        "状态": {"select": {"name": "已确定"}},
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


if __name__ == "__main__":
    unittest.main()
