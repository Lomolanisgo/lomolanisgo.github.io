#!/usr/bin/env python3
"""Rebuild the complete NIKL 2003 learner vocabulary from pinned source snapshots."""
import argparse
import csv
import hashlib
import html
import io
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parent
OFFICIAL = 'https://www.korean.go.kr/front/etcData/etcDataView.do?etc_seq=70&mn_id=46&pageIndex=1'
THIRD = 'https://topikvocab.foldalpha.com/download/'
URLS = {
    'nikl_2003.txt': 'https://www.korean.go.kr/common/download.do?c_file_name=b73a8438-4713-4436-8481-ec26fd0dce2a_0.txt&file_path=etcData&o_file_name=vocabulary.txt',
    'foldalpha_zh.csv': THIRD + 'topik-vocab-zh.csv',
    'foldalpha_en.csv': THIRD + 'topik-vocab-en.csv',
}
FIELDS = ['ID', 'Korean', 'Hanja', 'Chinese', 'English', 'POS', 'Level',
          'Word_Type', 'Pronunciation', 'Example', 'Example_CN', 'Source']
POS = dict(zip(['감','고','관','대','동','명','보','부','불','수','의','형'],
               ['感叹词','专有名词','冠形词','代词','动词','名词','辅助谓词','副词','不可分析','数词','依存名词','形容词']))
LEVEL = {'A': '初级（A／1阶段）', 'B': '中级（B／2阶段）', 'C': '高级（C／3阶段）'}
CJK = r'\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff'


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sources(raw, download):
    manifest_path = raw / 'manifest.json'
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if download:
        # Download to memory and validate before replacing any cached input.
        fetched = {}
        for name, url in URLS.items():
            response = requests.get(url, timeout=(20, 120))
            response.raise_for_status()
            data = response.content
            if name.endswith('.txt'):
                assert data.decode('cp949').startswith('순위\t단어\t품사'), 'Invalid official response'
            else:
                assert len(list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))) == 5965
            fetched[name] = data
        for name, data in fetched.items():
            (raw / name).write_bytes(data)
        old = None
    records = {}
    for name, url in URLS.items():
        data = (raw / name).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if old and old['files'][name]['sha256'] != digest:
            raise ValueError(f'Snapshot checksum mismatch: {name}')
        records[name] = {'url': url, 'sha256': digest, 'bytes': len(data)}
    if not old:
        dump(manifest_path, {'snapshot_recorded_utc': datetime.now(timezone.utc).isoformat(),
                             'files': records})


def origin(note):
    """Only classify explicit origin notation; absent origin is NOT evidence of native origin."""
    prefix = html.unescape(note).split('.')[0].strip().replace('\xad', '-')
    chars = ''.join(re.findall(f'[{CJK}]', prefix))
    if chars and re.fullmatch(f'[{CJK}]+', prefix):
        return chars, '汉字词', '原语全部为汉字'
    if chars and re.fullmatch(f'[{CJK}A-Za-z -]+', prefix):
        return chars, '混合词', '原语含汉字与外语或固有成分占位符'
    foreign = re.sub(r'^&[가-힣]+', '', prefix)
    if re.fullmatch(r'[A-Za-z][A-Za-z .’\x27-]*', foreign):
        return '', '外来词', '原语为拉丁字母（可含语言标记）'
    return chars, '', '词源未确认'


def build(raw, official_only=False):
    original = list(csv.DictReader(io.StringIO((raw / 'nikl_2003.txt').read_bytes().decode('cp949')), delimiter='\t'))
    assert len(original) == 5965
    assert Counter(r['등급'] for r in original) == {'A': 982, 'B': 2111, 'C': 2872}
    def key(r):
        return re.sub(r'\d+$', '', r['단어']), r['품사'], r['순위'], r['등급']
    official_keys = Counter(key(r) for r in original)
    assert max(official_keys.values()) == 1
    lookups, validation = {}, {}
    for lang in ('zh', 'en'):
        third = list(csv.DictReader(io.StringIO((raw / f'foldalpha_{lang}.csv').read_text(encoding='utf-8-sig'))))
        lookup = defaultdict(list)
        for r in third:
            lookup[(r['word'], r['pos'], r['freq_rank'], r['nikl_grade'][0])].append(r)
        third_keys = Counter({k: len(v) for k, v in lookup.items()})
        missing, extra = official_keys - third_keys, third_keys - official_keys
        validation[lang] = {'rows': len(third), 'missing': list(missing.elements()),
                            'extra': list(extra.elements()), 'duplicate_keys': sum(v-1 for v in third_keys.values()),
                            'matched': sum((official_keys & third_keys).values())}
        if missing or extra:
            raise ValueError(f'Third-party identity mismatch ({lang}): {validation[lang]}')
        lookups[lang] = {k: v[0] for k, v in lookup.items() if len(v) == 1}
    rows, provenance, disagreements = [], [], []
    for r in original:
        k = key(r)
        zh, en = lookups['zh'][k], lookups['en'][k]
        hanja, kind, basis = origin(r['풀이'])
        # Preserve original compatibility ideographs; never simplify Hanja.
        identifier = 'NIKL2003-' + hashlib.sha256((r['단어'] + '|' + r['품사']).encode()).hexdigest()[:16]
        row = dict.fromkeys(FIELDS, '')
        row.update(ID=identifier, Korean=k[0], Hanja=hanja, POS=POS[r['품사']],
                   Level=LEVEL[r['등급']], Word_Type=kind, Source=OFFICIAL)
        if not official_only:
            row.update(Chinese=zh['meaning'], English=en['meaning'], Example=zh['example_ko'],
                       Example_CN=zh['example_translation'],
                       Source=OFFICIAL + ' ; 第三方释义与例句（非官方）: ' + THIRD)
        for lang, other in [('zh', zh), ('en', en)]:
            # Compare Hanja only, ignoring placeholder hyphens and compatibility forms for comparison.
            import unicodedata
            other_hanja = ''.join(re.findall(f'[{CJK}]', other['hanja']))
            if unicodedata.normalize('NFKC', hanja) != unicodedata.normalize('NFKC', other_hanja):
                disagreements.append({'ID': identifier, 'language': lang, 'official': hanja, 'third_party': other['hanja']})
        provenance.append({'ID': identifier, 'Official_Word': r['단어'], 'Homonym_Number': re.search(r'\d+$', r['단어']).group() if re.search(r'\d+$', r['단어']) else '',
                           'Official_POS': r['품사'], 'Official_Grade': r['등급'], 'Frequency_Rank': r['순위'],
                           'Official_Note': r['풀이'], 'Word_Type_Basis': basis,
                           'Translation_Status': 'omitted' if official_only else 'third_party_not_officially_verified',
                           'Third_Party_Row': zh['no']})
        rows.append(row)
    assert len({r['ID'] for r in rows}) == len(rows), 'Identity collision'
    validation['hanja_disagreements'] = disagreements
    validation['translation_validation'] = 'Identity and coverage verified, NOT translation accuracy; official Hanja takes precedence.'
    return rows, provenance, validation


def statistics(rows):
    n = len(rows)
    kinds = Counter(r['Word_Type'] or '未确认' for r in rows)
    return {'total': n, 'levels': dict(Counter(r['Level'] for r in rows)),
            'pos': dict(Counter(r['POS'] for r in rows)),
            'word_types': {k: {'count': kinds[k], 'percent': round(kinds[k] / n * 100, 4)} for k in ['汉字词','固有词','外来词','混合词','未确认']},
            'word_type_note': '固有词 0 表示尚未确认，不表示词表没有固有词。分类依据原语标注规则，不是官方独立词源标签。',
            'has_hanja': sum(bool(r['Hanja']) for r in rows),
            'duplicate_ids': n - len({r['ID'] for r in rows}),
            'duplicate_full_rows': n - len({tuple(r.values()) for r in rows}),
            'repeated_headword_excess_rows': n - len({r['Korean'] for r in rows}),
            'missing_fields': {f: sum(not r[f] for r in rows) for f in FIELDS}}


def export(rows, provenance, validation, out):
    out.mkdir(parents=True, exist_ok=True)
    stats = statistics(rows)
    dump(out / 'vocabulary.json', rows)
    dump(out / 'provenance.json', provenance)
    dump(out / 'validation_report.json', validation)
    dump(out / 'quality_report.json', stats)
    with (out / 'vocabulary.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    # ID first prevents Anki from merging homographs. Escape HTML and flatten newlines.
    with (out / 'anki.tsv').open('w', encoding='utf-8', newline='') as f:
        f.write('#separator:tab\n#html:true\n#tags column:13\n#columns:' + '\t'.join(FIELDS + ['Tags']) + '\n')
        writer = csv.writer(f, delimiter='\t', lineterminator='\n')
        for r, p in zip(rows, provenance):
            cells = [html.escape(r[k]).replace('\t',' ').replace('\r','').replace('\n','<br>') for k in FIELDS]
            writer.writerow(cells + [f"NIKL2003::{p['Official_Grade']} WordType::{r['Word_Type'] or '未确认'}"])
    with sqlite3.connect(out / 'vocabulary.db') as con:
        con.execute('DROP TABLE IF EXISTS vocabulary')
        con.execute('DROP TABLE IF EXISTS provenance')
        con.execute('CREATE TABLE vocabulary (' + ','.join(f'"{f}" TEXT NOT NULL' + (' PRIMARY KEY' if f == 'ID' else '') for f in FIELDS) + ')')
        con.executemany('INSERT INTO vocabulary VALUES (' + ','.join('?' for _ in FIELDS) + ')', [tuple(r[f] for f in FIELDS) for r in rows])
        con.execute('CREATE INDEX idx_word ON vocabulary(Korean)')
        con.execute('CREATE INDEX idx_level_type ON vocabulary(Level, Word_Type)')
        con.execute('CREATE TABLE provenance (ID TEXT PRIMARY KEY REFERENCES vocabulary(ID), details TEXT NOT NULL)')
        con.executemany('INSERT INTO provenance VALUES (?,?)', [(p['ID'], json.dumps(p, ensure_ascii=False)) for p in provenance])
        assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    wb = Workbook()
    ws = wb.active
    ws.title = 'Vocabulary'
    ws.append(FIELDS)
    for r in rows:
        ws.append([r[f] for f in FIELDS])
    ws.freeze_panes = 'C2'
    widths = [31,21,20,36,40,16,24,16,20,70,60,70]
    from openpyxl.utils import get_column_letter
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    for cell in ws[1]:
        cell.fill = PatternFill('solid', fgColor='243746')
        cell.font = Font(color='FFFFFF', bold=True)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.data_type = 's'  # Source text must not become executable spreadsheet formulas.
            cell.alignment = Alignment(vertical='top', wrap_text=True)
    for i in range(2, len(rows)+2):
        ws.row_dimensions[i].height = 60
    table = Table(displayName='VocabularyTable', ref=f'A1:L{len(rows)+1}')
    table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
    ws.add_table(table)
    info = wb.create_sheet('说明与统计')
    for row in [('项目','内容'), ('官方来源',OFFICIAL), ('补充来源',THIRD),
                ('分级','2003 年 A/B/C 三阶段；初中高为显示标签，不等同 TOPIK 1–6 级。'),
                ('补充字段','中文、英文、韩语例句和例句译文为第三方内容；未逐句获官方核验。'),
                ('词源','依据官方原语标注推导；无充分证据留空。固有词 0 不是不存在。'),
                ('汉字','保留官方传统字及兼容字形；混合词仅显示其中汉字成分。'),
                ('发音','官方词典下载被防火墙拦截，标准发音全部留空。'),
                ('总数',len(rows))]:
        info.append(row)
    for section in ('levels','pos','missing_fields'):
        for k,v in stats[section].items(): info.append((section + ': ' + k,v))
    for k,v in stats['word_types'].items(): info.append(('词源: '+k, f"{v['count']} ({v['percent']}%)"))
    info.column_dimensions['A'].width = 38
    info.column_dimensions['B'].width = 110
    for row in info:
        for c in row: c.alignment = Alignment(wrap_text=True, vertical='top')
    wb.save(out / 'vocabulary.xlsx')
    check = load_workbook(out / 'vocabulary.xlsx')
    assert check['Vocabulary'].max_row == len(rows)+1
    assert check['Vocabulary'].tables['VocabularyTable'].ref == f'A1:L{len(rows)+1}'
    assert check['Vocabulary'].freeze_panes == 'C2'
    # Verify every Excel field, including homographs and traditional Hanja.
    for actual, expected in zip(check['Vocabulary'].iter_rows(min_row=2, values_only=True), rows):
        assert tuple(x or '' for x in actual) == tuple(expected[f] for f in FIELDS)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Explicitly refresh all source snapshots from the network')
    parser.add_argument('--official-only', action='store_true', help='Omit third-party meanings and examples')
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    raw = ROOT / 'data' / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    sources(raw, args.download)
    export(*build(raw, args.official_only), args.output_dir)


if __name__ == '__main__':
    main()
