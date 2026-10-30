"""Build code-titled vehicle pages with WTJ dependencies and explicit retirement mapping."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from paths import ROOT, WIKI, WORK, IMPORT_PACK, reset_import_pack
from vehicle_page import dumps, load_json, xml_export, merge_ordnance_pages, verify_lua
from vehicle_demo_pack import query, has_local_image, BASE
from testing_cleanup import write_cleanup

OUT = WIKI / 'production/vehicle-pages'
EXAMPLES = [('vehicle-prototype', 'il_leopard_2a6_hel'), ('vehicle-prototype-mig35', 'mig_35'), ('vehicle-prototype-pe8', 'pe-8_m82')]
OLD = 'WTJTreeTesting-VehicleDemo20261027'


def replace_files(value, mapping):
    if isinstance(value, dict):
        return {k: replace_files(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_files(v, mapping) for v in value]
    return mapping.get(value, value) if isinstance(value, str) else value


def backup_current(pages, target):
    saved = []
    for start in range(0, len(pages), 15):
        params = urlencode({'action': 'query', 'format': 'json', 'prop': 'revisions',
                            'rvprop': 'content|timestamp|contentmodel', 'rvslots': 'main',
                            'titles': '|'.join(p['title'] for p in pages[start:start + 15])}).encode()
        with urlopen(Request(BASE + 'api.php', data=params, headers={'User-Agent': 'WTJ-read-only-backup/1.0'}), timeout=30) as response:
            raw = json.load(response)
        for page in raw['query']['pages'].values():
            if 'missing' in page:
                continue
            revision = page['revisions'][0]
            slot = revision['slots']['main']
            content = slot['*']
            saved.append({'title': page['title'], 'model': slot.get('contentmodel', revision.get('contentmodel', 'wikitext')),
                          'content': content, 'bytes': len(content.encode()), 'timestamp': revision['timestamp']})
    xml_export(saved, target)
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    audit_images = load_json(WIKI / 'production/game-image-audit/manifest.json')
    mapping = {a['filename']: a['wiki_file'].split(':', 1)[1] for a in audit_images['assets']
               if a['status'] in ('existing_alias', 'existing_original')}
    pages, assets, data_by_code, title_mapping = {}, {}, {}, {}
    for folder, code in EXAMPLES:
        bundle = load_json(WIKI / folder / 'manifest.json')
        assert bundle['title'] == code and bundle['validation']['two_modes'] == 'passed'
        data_by_code[code] = load_json(WIKI / folder / 'pages/data/vehicle' / (code + '.json'))
        for name, info in bundle['uploads'].items():
            target = mapping.get(name, name)
            source = WIKI / folder / 'uploads' / name
            if target in assets:
                assert source.read_bytes() == assets[target].read_bytes()
            assets[target] = source
        for original in bundle['pages']:
            page = dict(original)
            if page['model'] == 'json':
                page['content'] = dumps(replace_files(json.loads(page['content']), mapping))
            if page['title'] in pages:
                if '/data/ordnance/' in page['title']:
                    page['content'] = merge_ordnance_pages(pages[page['title']]['content'], page['content'])
                else:
                    assert pages[page['title']]['content'] == page['content'], page['title']
            page['bytes'] = len(page['content'].encode())
            pages[page['title']] = page
            if page['title'] == code:
                title_mapping[OLD + '/vehicle/' + code] = code
                title_mapping['WTJTreeTesting/vehicle/' + code] = code
            else:
                title_mapping[page['title'].replace('WTJ', OLD, 1)] = page['title']
                title_mapping[page['title'].replace('WTJ', 'WTJTreeTesting', 1)] = page['title']
        for kind in ('basic-info', 'player-content', 'user-content'):
            replacement = 'player-content' if kind == 'user-content' else kind
            title_mapping[OLD + '/vehicle/' + code + '/' + kind] = code + '/' + replacement
            title_mapping['WTJTreeTesting/vehicle/' + code + '/' + kind] = code + '/' + replacement
        title_mapping['文件:' + OLD + '_' + code + '.png'] = '文件:' + code + '_资料卡.png'
    title_mapping['文件:' + OLD + '_mod_agm_glide_missile.png'] = '文件:agm_glide_missile.png'
    values = list(pages.values())
    assert not any(re.search(r'Testing|Demo2026', p['title'] + p['content']) for p in values)
    assert not any(p['title'].endswith(('/basic-info', '/player-content')) for p in values)
    preview_uploads = OUT / 'preview/uploads'
    preview_uploads.mkdir(parents=True, exist_ok=True)
    for name, source in assets.items():
        shutil.copyfile(source, preview_uploads / name)
    renders = {}
    for _, code in EXAMPLES:
        data = replace_files(data_by_code[code], mapping)
        if data.get('ordnance_pages'):
            data['aircraft_catalog'] = {key: item for title in data['ordnance_pages']
                                        for key, item in json.loads(pages[title]['content'])['items'].items()}
        _, renders[code] = verify_lua(data, ROOT / 'src/vehicle.lua', values, OUT / 'preview' / code)
    targets = [p['title'] for p in values] + ['文件:' + name for name in assets]
    site = query(targets)
    unknown = [title for title, record in site.items() if record['status'] == 'unknown']
    if unknown:
        raise RuntimeError('Unknown targets: ' + str(unknown))
    missing = [name for name in assets if not has_local_image(site['文件:' + name].get('record'))]
    assert all(site['文件:' + name]['status'] == 'missing' for name in missing)
    for filename, subset in [('01-data-and-modules.xml', [p for p in values if p['model'] in ('json', 'Scribunto')]),
                             ('02-templates-and-controls.xml', [p for p in values if p['title'].startswith(('模板:', 'MediaWiki:'))]),
                             ('03-vehicle-articles.xml', [p for p in values if p['title'] in data_by_code])]:
        xml_export(subset, OUT / 'Slices' / filename)
    xml_export(values, OUT / 'Full/WTJ-vehicle-pages.xml')
    saved = backup_current(values, OUT / 'Rollback/WTJ-vehicle-pages-before.xml')
    (OUT / 'title-mapping.json').write_text(dumps(title_mapping, True), encoding='utf-8')
    cleanup = write_cleanup(OUT / 'Cleanup', targets, active_contents=[p['content'] for p in values])
    actions = [{'title': p['title'], 'model': p['model'], 'operation': 'update' if site[p['title']]['status'] == 'existing' else 'create',
                'url': BASE + 'index.php?' + urlencode({'title': p['title']})} for p in values]
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'prefix': 'WTJ', 'pages': len(values),
              'articles': list(data_by_code), 'actions': actions, 'missing_images': missing, 'site': site,
              'lua_validation': renders, 'title_mapping': title_mapping, 'rollback_pages': len(saved),
              'live_wiki_written': False, 'xml_files': {p.relative_to(OUT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in ('Full', 'Slices', 'Rollback') for p in (OUT / folder).glob('*.xml')}}
    if args.publish:
        css_check = load_json(WIKI / 'vehicle-prototype/site-parse-validation.json')
        assert css_check['passed'] and css_check['css_sha256'] == hashlib.sha256((ROOT / 'src/vehicle.css').read_text(encoding='utf-8').encode()).hexdigest()
        browser = load_json(OUT / 'browser-validation.json')
        assert {(r['code'], r['width']) for r in browser} == {(code, width) for _, code in EXAMPLES for width in (1440, 390)}
        assert all(not r['errors'] and r['editTargets'] == 'passed' for r in browser)
        archive = WORK / 'history' / ('ImportPack-before-formal-vehicles-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
        shutil.copytree(IMPORT_PACK, archive)
        destination = reset_import_pack()
        for folder in ('Full', 'Slices', 'Rollback'):
            shutil.copytree(OUT / folder, destination / folder)
        for name in missing:
            shutil.copyfile(assets[name], destination / name)
        report['import_pack'] = str(destination)
        report['previous_pack_saved'] = str(archive)
    (OUT / 'manifest.json').write_text(dumps(report, True), encoding='utf-8')
    lines = ['# 载具页面导入清单', '', '文章标题使用载具代码；模块、模板、数据与脚本使用 WTJ 共用名称。', '',
             '小图 `<代码>.png`；资料卡大图 `<代码>_资料卡.png`，图片原始内容不变。', '',
             '## 精确标题与操作', '', '| 标题 | 内容模型 | 操作 |', '|---|---|---|']
    lines += [f"| `{a['title']}` | {a['model']} | {a['operation']} |" for a in actions]
    lines += ['', '## 图片', '', *['- `文件:' + n + '`' for n in missing], '',
              '完整全站图片补充见 ../game-image-audit/DELIVERY.md，统一后缀，不再使用测试文件名。', '',
              '## 导入与清理（必做）', '',
              '1. 导入前再次 Special:Export 备份当前页面；Rollback 含本次只读取得的现存页修订。',
              '2. 上传缺失图片，再依次导入 Slices 三片；Full 与 Slices 二选一。',
              '3. 人工内容子页为 `<代码>/basic-info` 和 `<代码>/player-content`，不在常规导入包中。先备份并迁移旧测试子页内容。',
              '4. 验收正式文章、模式切换、模板与图片引用后，按 title-mapping.json 检查链入，再删除旧测试页。',
              '5. 使用 [清理说明](Cleanup/CLEANUP.md) 和 [管理员删除入口](Cleanup/CLEANUP.html)，删除后重新查存在性及删除日志。XML 导入不能删除页。', '',
              '本次仅本地生成、浏览器验证和只读站点查询；没有执行线上导入、移动或删除。']
    (OUT / 'UPLOAD-LIST.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(dumps({k: report[k] for k in ('pages', 'articles', 'missing_images', 'rollback_pages', 'live_wiki_written')}, True))


if __name__ == '__main__':
    main()
