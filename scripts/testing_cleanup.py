"""Inventory historical test titles and generate offline administrator cleanup aids.

Never logs in or writes to the Wiki. --refresh-site performs public read-only queries.
Local XML/manifest presence is evidence of generation, not evidence of import.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from paths import ROOT, WIKI, WORK, IMPORT_PACK

BASE = 'https://wiki.biligame.com/warthunder/'
OUT = WORK / 'reports/testing-cleanup'
FAMILIES = ('WTJTesting', 'WTJClassTesting', 'WTJRegistryTesting', 'WTJTreeTesting')
PATTERN = re.compile(r'^(?:(?:模块|Module|模板|Template|MediaWiki):)?(WTJ(?:Tree|Class|Registry)?Testing)(?=[/ _.-]|$)')
SCREENSHOT = 'codex-clipboard-be01c2a2-6e61-41df-8572-d343cadc6b19.png'
DEMO = 'WTJTreeTesting-VehicleDemo20261027'
SCREENSHOT_TITLES = (
    [DEMO + '/data/vehicle/' + c + '.json' for c in ('il_leopard_2a6_hel', 'mig_35', 'pe-8_m82')]
    + ['模块:' + DEMO + '/' + m for m in ('vehicle', 'modifications', 'vehicle-content', 'loadouts')]
    + ['模板:' + DEMO + '/' + t for t in ('modifications', 'vehicle-content', 'vehicle-styles', 'vehicle-page')]
    + ['MediaWiki:' + DEMO + '-vehicle.js']
    + [DEMO + '/data/ordnance/aircraft-' + str(i) + '.json' for i in range(4)]
    + [DEMO + '/vehicle/' + c for c in ('il_leopard_2a6_hel', 'mig_35', 'pe-8_m82')]
)


def canonical(title):
    title = title.replace('_', ' ').strip()
    for old, new in (('Module:', '模块:'), ('Template:', '模板:'), ('File:', '文件:'), ('User:', '用户:')):
        if title.startswith(old):
            title = new + title[len(old):]
    return title


def family(title):
    target = title.split(':', 1)[-1] if title.startswith(('文件:', 'File:')) else title
    match = PATTERN.match(target)
    if match:
        return match[1]
    if canonical(title) == canonical('文件:us_m1a2_abrams_json_testing.png'):
        return 'WTJTesting'
    if re.fullmatch(r'(?:用户|User):319206634/WTJTreeTesting\.(?:css|js)', title):
        return 'WTJTreeTesting'
    return None


def xml_titles(path):
    return [node.text for _, node in ET.iterparse(path, events=('end',))
            if node.tag.rsplit('}', 1)[-1] == 'title' and node.text]


def api(**params):
    request = Request(BASE + 'api.php', data=urlencode({'format': 'json', **params}).encode(),
                      headers={'User-Agent': 'WTJ-cleanup-inventory/1.0 (read-only)',
                               'Content-Type': 'application/x-www-form-urlencoded'})
    with urlopen(request, timeout=15) as response:
        data = json.load(response)
    if 'error' in data:
        raise RuntimeError(str(data['error']))
    return data


def inventory(refresh_site=False):
    OUT.mkdir(parents=True, exist_ok=True)
    registry = OUT / 'inventory.json'
    previous = json.loads(registry.read_text(encoding='utf-8')) if registry.exists() else {}
    records = {}
    for old in previous.get('pages', []):
        key = canonical(old['title'])
        if key not in records:
            records[key] = {**old, 'title': key, 'sources': list(old['sources']), 'evidence': list(old['evidence'])}
        else:
            row = records[key]
            row['sources'] = sorted(set(row['sources'] + old['sources']))
            row['evidence'] = sorted(set(row['evidence'] + old['evidence']))
            if old.get('site_checked_at', '') > row.get('site_checked_at', ''):
                row.update(site_status=old['site_status'], site_checked_at=old['site_checked_at'])
    errors = list(previous.get('errors', [])) if not refresh_site else []

    def add(title, source, evidence='local-generated'):
        group = family(title)
        if not group:
            return
        title = canonical(title)
        row = records.setdefault(title, {'title': title, 'family': group, 'sources': [],
                                        'evidence': [], 'site_status': 'unknown'})
        if source not in row['sources']:
            row['sources'].append(source)
        if evidence not in row['evidence']:
            row['evidence'].append(evidence)

    # Scan page declarations only, never every linked title or reused file reference.
    def walk(value, source):
        if isinstance(value, dict):
            if isinstance(value.get('title'), str):
                add(value['title'], source)
            uploads = value.get('uploads')
            if isinstance(uploads, (dict, list)):
                for filename in uploads:
                    if isinstance(filename, str):
                        add('文件:' + filename, source, 'local-upload-candidate')
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child, source)
        elif isinstance(value, list):
            for child in value:
                walk(child, source)

    for directory in (WIKI, WORK / 'history', WORK / 'exports', ROOT / 'evidence', IMPORT_PACK):
        if not directory.exists():
            continue
        for path in sorted(directory.rglob('*')):
            if not path.is_file() or path.is_symlink():
                continue
            source = str(path.relative_to(ROOT.parent)).replace('\\', '/')
            try:
                if path.suffix == '.xml':
                    for title in xml_titles(path):
                        add(title, source)
                elif path.suffix == '.json' and 'manifest' in path.name:
                    walk(json.loads(path.read_text(encoding='utf-8-sig')), source)
            except (ET.ParseError, ValueError, OSError) as exc:
                errors.append(source + ': ' + str(exc))
    old = OUT / 'all-testing-pages.txt'
    if old.exists():
        for title in old.read_text(encoding='utf-8').splitlines():
            add(title, 'historical all-testing-pages.txt', 'historical-inventory')
    for title in SCREENSHOT_TITLES:
        add(title, SCREENSHOT, 'screenshot-import-confirmed')
    for title in ('用户:319206634/WTJTreeTesting.js', '用户:319206634/WTJTreeTesting.css'):
        add(title, '2026-10-23 historical cleanup README', 'manual-review')
    add('文件:us_m1a2_abrams_json_testing.png', 'historical M1A2 page-manifest.json image field', 'local-upload-candidate')
    add('WTJTreeTesting/tree_testing.js', 'historical source-query title; existence unconfirmed', 'manual-review')
    # These optional human-content pages are never generated by routine imports.
    for title in list(records):
        if '/vehicle/' in title and not title.endswith(('.json', '/basic-info', '/player-content', '/user-content')):
            for suffix in ('basic-info', 'player-content', 'user-content'):
                add(title + '/' + suffix, 'possible manually created subpage of ' + title, 'possible-human-content')

    if refresh_site:
        checked_at = datetime.now(timezone.utc).isoformat()
        try:
            # Include undocumented descendants and namespace variants; preserve continuation.
            for ns in (0, 6, 8, 10, 828):
                for prefix in FAMILIES:
                    continuation = {}
                    while True:
                        data = api(action='query', list='allpages', apnamespace=ns,
                                   apprefix=prefix, aplimit=500, **continuation)
                        for page in data['query']['allpages']:
                            add(page['title'], 'API allpages at ' + checked_at, 'site-discovered')
                        continuation = data.get('continue', {})
                        if not continuation:
                            break
        except Exception as exc:
            errors.append('Online prefix discovery incomplete: ' + str(exc))
        titles = sorted(records)
        for start in range(0, len(titles), 25):
            batch = titles[start:start + 25]
            try:
                data = api(action='query', titles='|'.join(batch), prop='info')
                by_title = {canonical(p['title']): p for p in data['query']['pages'].values()}
                normalized = {canonical(p['from']): canonical(p['to'])
                              for p in data['query'].get('normalized', [])}
                for title in batch:
                    key = canonical(title)
                    page = by_title.get(normalized.get(key, key))
                    status = 'unknown' if page is None or 'invalid' in page else 'missing' if 'missing' in page else 'existing'
                    records[title].update(site_status=status, site_checked_at=checked_at)
            except Exception as exc:
                errors.append('Online title check failed: ' + str(exc))
                for title in batch:
                    if records[title]['site_status'] in ('existing', 'missing'):
                        records[title]['last_successful_site_status'] = records[title]['site_status']
                        records[title]['last_successful_checked_at'] = records[title].get('site_checked_at')
                    records[title].update(site_status='unknown', site_checked_at=checked_at)
                break  # Do not repeatedly hit an unavailable site.
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'live_wiki_written': False,
              'errors': errors, 'pages': sorted(records.values(), key=lambda row: row['title'])}
    registry.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def write_cleanup(output, active_titles=(), refresh_site=False, active_contents=()):
    """Called by import-list generators; active titles are held until replacement retires them."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report = inventory(refresh_site)
    active = {canonical(title) for title in active_titles}
    contents = list(active_contents)
    # An existing delivery remains active until a replacement is explicitly supplied.
    if not active:
        for path in (IMPORT_PACK / 'Full').glob('*.xml'):
            active.update(canonical(title) for title in xml_titles(path))
            contents.append(path.read_text(encoding='utf-8'))
        if IMPORT_PACK.exists():
            active.update(canonical('文件:' + p.name) for p in IMPORT_PACK.iterdir()
                          if p.is_file() and p.suffix.lower() in ('.png', '.svg', '.jpg'))
    contents = [canonical(content) for content in contents]
    rows = []
    for original in report['pages']:
        row = dict(original)
        title = row['title']
        aliases = {canonical(title)}
        if title.startswith(('模块:', '模板:', '文件:')):
            aliases.add(canonical(title.split(':', 1)[1]))
        row['disposition'] = ('hold-current-import' if canonical(title) in active or any(alias in content for alias in aliases for content in contents) else
                              'review-file-usage' if title.startswith(('文件:', 'File:')) else
                              'preserve-human-content' if title.endswith(('/basic-info', '/player-content', '/user-content')) else
                              'review-personal-loader' if title.startswith(('用户:', 'User:')) else
                              'retire-after-dependency-check')
        rows.append(row)
    report = {**report, 'pages': rows, 'active_import_titles': sorted(active)}
    (output / 'cleanup-inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (output / 'cleanup-pages.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['title', 'family', 'disposition', 'site_status', 'site_checked_at', 'evidence', 'sources'])
        for row in rows:
            writer.writerow([row['title'], row['family'], row['disposition'], row['site_status'],
                             row.get('site_checked_at', ''), '; '.join(row['evidence']), '; '.join(row['sources'])])
    for filename, subset in (
        ('cleanup-export-pages.txt', rows),
        ('cleanup-existing-pages.txt', [r for r in rows if r['site_status'] == 'existing']),
        ('cleanup-retire-candidates.txt', [r for r in rows if r['disposition'] == 'retire-after-dependency-check']),
    ):
        (output / filename).write_text(''.join(r['title'] + '\n' for r in subset), encoding='utf-8')
    counts = Counter(r['family'] for r in rows)
    statuses = Counter(r['site_status'] for r in rows)
    confirmed = sum('screenshot-import-confirmed' in r['evidence'] for r in rows)
    note = ('# 历史测试页面清理清单\n\n'
            f'共 {len(rows)} 项候选，截图确认曾导入 {confirmed} 个不同标题。截图重复行已去重。'
            '空格与下划线及中英文命名空间别名已合并。本地生成不等于线上存在；site_status 和核对时间见 CSV。\n\n'
            f"最近记录：存在 {statuses['existing']}，缺失 {statuses['missing']}，未知 {statuses['unknown']}。存在标题另见 cleanup-existing-pages.txt；不代表这些页均可直接删除。\n\n"
            + '\n'.join(f'- {key}：{value} 项' for key, value in sorted(counts.items()))
            + '\n\n每次导入均须处理此清单。先用 cleanup-export-pages.txt 从 Special:Export 保存线上当前修订；'
            '导入替代页并验证链接、模板和脚本后，删除退休测试页，最后核查删除日志并重新查询存在性。'
            'XML 导入不能删除页面；空白页、重定向也不算删除。\n\n'
            '打开 CLEANUP.html 可搜索精确标题，并进入查看、链入、文件用途和管理员删除页。'
            '候选文本用于核对，不能直接当作已经确认安全的批量删除输入。'
            '本次导入仍使用的标题标为 hold-current-import，必须在采用稳定正式标题的替代包验收后退休，不能边导入边删除。'
            '人工内容子页先迁移到正式归属并备份；文件先查用途；个人 common.js 只移除测试加载片段。\n\n'
            '保留正式 WTJ 页面、科技树、Tr/数据库、ResourceLoader、Common.js、Item/Specs 背景及复用图标。'
            '旧 SMW 页等未留下精确标题的页面仍需从站内贡献、导入/移动日志补查；不得按含 testing 的模糊匹配删除。'
            '普通页面导出不包含图片二进制，清理文件前另存原图；确认已移动的旧名不意味着可以删除新名文件。\n\n'
            '生成器只读查询或本地写文件，没有执行线上删除。完整要求见 docs/TEST-PAGE-CLEANUP.md。\n')
    if report['errors']:
        note += '\n核对未完成：\n' + '\n'.join('- ' + error for error in report['errors']) + '\n'
    (output / 'CLEANUP.md').write_text(note, encoding='utf-8')
    if output.resolve() == OUT.resolve():
        readme = output / 'README.md'
        archive = output / 'README-historical-20261023.md'
        if readme.exists() and not archive.exists():
            archive.write_text(readme.read_text(encoding='utf-8'), encoding='utf-8')
        readme.write_text('# 当前测试页清理入口\n\n请使用 [CLEANUP.md](CLEANUP.md)、[管理员入口](CLEANUP.html) 和 [完整清单](cleanup-pages.csv)。\n\n'
                          '旧 all-testing-pages.txt、remaining-demo-pages.txt、replaced-tree-pages.txt 及 README-historical-20261023.md 仅为 2026-10-23 历史证据；旧 37 页统计已过期，不作为当前删除清单。\n', encoding='utf-8')
    table = []
    for row in rows:
        title = row['title']
        links = [('查看', {'title': title}), ('链入', {'title': 'Special:WhatLinksHere/' + title}),
                 ('删除', {'title': title, 'action': 'delete'})]
        if title.startswith(('文件:', 'File:')):
            links.insert(2, ('文件用途', {'title': title}))
        anchors = ' · '.join('<a target="_blank" rel="noopener" href="' + html.escape(BASE + 'index.php?' + urlencode(p) + ('#filelinks' if label == '文件用途' else ''), quote=True) + '">' + label + '</a>' for label, p in links)
        table.append('<tr><td>' + html.escape(title) + '</td><td>' + html.escape(row['disposition']) + '</td><td>' + html.escape(row['site_status']) + '</td><td>' + anchors + '</td></tr>')
    (output / 'CLEANUP.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>历史测试页清理</title>'
        '<style>body{font:15px/1.6 system-ui;margin:24px}td,th{padding:8px;border:1px solid #ccc;text-align:left;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}input{width:90%;padding:10px}</style>'
        '<h1>历史测试页清理</h1><p>先备份并核对依赖，再由管理员删除。此页只提供入口，不自动提交删除。</p>'
        '<p><a href="CLEANUP.md">处理步骤与数量</a> · <a href="cleanup-pages.csv">完整来源清单</a> · <a href="cleanup-export-pages.txt">导出备份标题</a></p>'
        '<p>hold-current-import：当前导入仍使用；preserve-human-content：先备份迁移；review-file-usage：先查文件用途；其余候选也须检查链入。</p>'
        '<input id="search" placeholder="搜索标题、处理要求或线上状态" aria-label="搜索"><table><thead><tr><th>精确标题</th><th>处理要求</th><th>线上状态</th><th>管理员入口</th></tr></thead><tbody>'
        + ''.join(table) + '</tbody></table><script>document.getElementById("search").oninput=function(){for(const r of document.querySelectorAll("tbody tr"))r.hidden=!r.textContent.toLowerCase().includes(this.value.toLowerCase())}</script></html>', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-site', action='store_true')
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    result = write_cleanup(args.out, refresh_site=args.refresh_site)
    print(json.dumps({'directory': str(args.out.resolve()), 'candidates': len(result['pages']),
                      'errors': result['errors'], 'live_wiki_written': False}, ensure_ascii=False))
