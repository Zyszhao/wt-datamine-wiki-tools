"""Consolidate the current vehicle and image delivery; retire wrong-name packages.

No Wiki writes. Old generated pages are discarded, never used as source data or
redirect dependencies. Human-owned subpages are backed up before retirement.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import html
import json
import shutil
import subprocess
import sys
from urllib.parse import urlencode

from paths import ROOT, WIKI, WORK, IMPORT_PACK
from asset_naming import vehicle_image_name
from testing_cleanup import write_cleanup
from vehicle_demo_pack import query, BASE
from vehicle_pack import backup_current
from verify_vehicle_uploads import pages

OUT = WIKI / 'production/vehicle-pages'


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(script, *args):
    subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *args], cwd=ROOT, check=True)


def retire(manifest):
    mapping = dict(manifest['title_mapping'])
    # The briefly generated English suffix is also retired. Query exact names;
    # local generation alone does not establish that those files were uploaded.
    for code in manifest['articles']:
        mapping['文件:' + code + '_statcard.png'] = '文件:' + vehicle_image_name(code + '.png', large=True)
    status = query(sorted(mapping))
    unknown = [title for title, record in status.items() if record['status'] == 'unknown']
    if unknown:
        dump(OUT / 'RETIREMENT-QUERY.json', status)
        raise RuntimeError('Old-name queries incomplete: ' + str(unknown))
    backup_targets = [{'title': title} for title, record in status.items()
                      if record['status'] == 'existing' and not title.startswith('文件:')]
    # Backups belong outside ImportPack: importing these would resurrect old names.
    retirement = OUT / 'Retired'
    retirement.mkdir(exist_ok=True)
    saved = backup_current(backup_targets, retirement / 'existing-wrong-name-pages-backup.xml')
    if len(saved) != len(backup_targets):
        raise RuntimeError('Old-page backup incomplete; review exact targets before retirement')
    dump(retirement / 'site-evidence.json', status)
    rows = []
    for old, new in sorted(mapping.items()):
        human = old.endswith(('/basic-info', '/player-content', '/user-content'))
        file = old.startswith('文件:')
        instruction = ('先另存图片并检查用途；替代图片验收后删除旧文件' if file else
                       '保留并迁移人工内容，确认备份后删除旧子页' if human else
                       '整页弃用；正式替代验收并检查链入后删除，不导入旧源码、不保留重定向')
        row = {'old_title': old, 'replacement': new, 'site_status': status[old]['status'],
               'resolved_title': (status[old].get('record') or {}).get('title'),
               'kind': 'file' if file else 'human-content' if human else 'generated-page',
               'instruction': instruction, 'delete_url': BASE + 'index.php?' + urlencode({'title': old, 'action': 'delete'}),
               'backlinks_url': BASE + 'index.php?' + urlencode({'title': 'Special:WhatLinksHere/' + old})}
        rows.append(row)
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'policy': 'discard-wrong-name-generated-pages',
              'no_redirect_dependency': True, 'old_generated_sources_reused': False,
              'online_deletions_performed': False, 'counts': dict(Counter(row['site_status'] for row in rows)),
              'backup_pages': len(saved), 'records': rows}
    dump(retirement / 'retirement.json', report)
    (retirement / 'existing-pages-to-review.txt').write_text(''.join(row['old_title'] + '\n' for row in rows
                         if row['site_status'] == 'existing'), encoding='utf-8')
    lines = ['# 错误命名载具包：全盘弃用', '',
             '旧生成页面全部弃用。新包从当前源码和载具数据重建，不导入旧生成页、不以旧名重定向作为依赖。',
             '人工内容子页先备份迁移；文件先检查用途并另存原图。仅存在且依赖已退出的旧标题进入管理员删除步骤。', '',
             f"本次精确核对 {len(rows)} 个旧标题：存在 {report['counts'].get('existing', 0)}，缺失 {report['counts'].get('missing', 0)}。",
             f'已只读备份 {len(saved)} 个现存页面修订，备份不在 ImportPack；不要将此备份当作新版本导入。', '',
             '[管理员逐项删除入口](DELETE.html) · [全部历史测试页清理](../Cleanup/CLEANUP.html)', '',
             '| 旧标题 | 正式替代 | 当前状态 | 处理 |', '|---|---|---|---|']
    lines += [f"| `{r['old_title']}` | `{r['replacement']}` | {r['site_status']} | {r['instruction']} |" for r in rows]
    lines += ['', '删除后重新查询存在性和删除日志。本地弃用、导入 XML 或重定向均不等于线上删除。']
    (retirement / 'RETIREMENT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    table = ''.join('<tr><td>' + html.escape(r['old_title']) + '</td><td>' + html.escape(r['replacement']) +
                    '</td><td>' + r['site_status'] + '</td><td>' + html.escape(r['instruction']) +
                    '</td><td><a target="_blank" href="' + html.escape(r['backlinks_url'], quote=True) + '">检查链入</a> · ' +
                    '<a target="_blank" href="' + html.escape(r['delete_url'], quote=True) + '">管理员删除</a></td></tr>' for r in rows)
    (retirement / 'DELETE.html').write_text('<!doctype html><meta charset="utf-8"><title>错误命名载具页弃用</title>'
        '<style>body{font:15px/1.6 system-ui;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px}</style>'
        '<h1>旧载具包全盘弃用</h1><p>先备份并验收正式替代，再检查链入、人工内容和文件用途，最后删除。此工具不提交删除。</p>'
        '<table><tr><th>旧标题</th><th>正式替代</th><th>状态</th><th>处理</th><th>操作</th></tr>' + table + '</table>', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='Rebuild the agreed ImportPack before consolidating')
    args = parser.parse_args()
    if args.publish:
        run('vehicle_pack.py', '--publish')
        run('audit_game_images.py', '--reuse-inventory', '--publish')
    run('verify_vehicle_uploads.py')
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
    full = pages(IMPORT_PACK / 'Full/WTJ-vehicle-pages.xml')
    assert not any('Testing' in title + content or '_statcard.png' in content for title, (_, content) in full.items())
    cleanup = write_cleanup(OUT / 'Cleanup', list(full), refresh_site=True,
                            active_contents=[content for _, content in full.values()])
    if cleanup['errors']:
        raise RuntimeError('Historical cleanup queries incomplete: ' + str(cleanup['errors']))
    assert not any(r['disposition'] == 'hold-current-import' for r in cleanup['pages'])
    retired = retire(manifest)
    legacy = (WIKI / 'production/vehicle-demo').resolve()
    legacy_archive = None
    if legacy.exists():
        assert legacy.parent == (WIKI / 'production').resolve() and not legacy.is_symlink()
        legacy_archive = (WORK / 'history' / ('retired-vehicle-demo-' + datetime.now().strftime('%Y%m%d-%H%M%S'))).resolve()
        assert legacy_archive.parent == (WORK / 'history').resolve() and not legacy_archive.exists()
        shutil.move(str(legacy), str(legacy_archive))
    slices = [{'file': p.relative_to(IMPORT_PACK).as_posix(), 'pages': len(pages(p))}
              for p in sorted((IMPORT_PACK / 'Slices').glob('*.xml'))]
    actual_images = [p for p in IMPORT_PACK.rglob('*') if p.suffix in ('.png', '.svg')]
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'import_pack': str(IMPORT_PACK),
              'pages': len(full), 'slices': slices, 'images': len(actual_images), 'articles': manifest['articles'],
              'old_packages': 'retired; never import old generated pages', 'old_generated_sources_reused': False,
              'retirement_counts': retired['counts'], 'retirement_backups_outside_import_pack': True,
              'legacy_local_package_archived_to': str(legacy_archive) if legacy_archive else None,
              'cleanup_query_errors': cleanup['errors'], 'live_wiki_written': False}
    dump(OUT / 'DELIVERY-MANIFEST.json', report)
    guide = ['# 当前载具页面与图片包', '', f'唯一导入目录：`{IMPORT_PACK}`。此前错误命名的载具页面包全部弃用。', '',
             f"本包 {len(full)} 页，三片 {' / '.join(str(s['pages']) for s in slices)} 页；待上传图片 {len(actual_images)} 张。",
             '文章使用载具代码；共用资源使用 WTJ；大图使用 `<代码>_资料卡.png`，兼容 MediaWiki 首字母大写。', '',
             '## 正式文章', '', *['- `' + code + '`' for code in manifest['articles']], '',
             '## 文件与导入顺序', '',
             '1. 只使用本次 ImportPack。先查看 [精确页面及图片清单](UPLOAD-LIST.md)。',
             '2. 上传 ImportPack 根目录的页面必需图片；[全站补图](../game-image-audit/DELIVERY.md)位于 SupplementalImages。已在站内的资源不重复交付。',
             '3. 依次导入以下三个切片，或只导入 Full 总包；两种方式二选一。', '',
             '| 文件 | 页数 |', '|---|---:|', *[f"| `{s['file']}` | {s['pages']} |" for s in slices], '',
             'Full 总包：`Full/WTJ-vehicle-pages.xml`。`Rollback/` 仅用于恢复本次导入前的正式标题，不是安装切片。',
             '两个人工内容子页 `<代码>/basic-info`、`<代码>/player-content` 不在常规包中。', '',
             '## 旧包全部弃用', '',
             '旧 Testing、Demo、日期前缀载具页及其生成依赖、错误英文后缀图片退出本次交付，不再继续导入或更新。',
             '不迁移旧生成源码，不依赖旧页重定向；人工编辑内容先备份保留。',
             '正式替代验收后，按 [专项弃用清单](Retired/RETIREMENT.md) 和 [管理员删除入口](Retired/DELETE.html)清理旧标题。',
             '全历史清理仍见 [CLEANUP.md](Cleanup/CLEANUP.md) 与 [管理员入口](Cleanup/CLEANUP.html)；其中其他功能的共享资源须另查依赖，不能随载具旧包一并误删。',
             '现存旧页面只读备份保存在 Retired 下，位于 ImportPack 之外；不能将该备份当作当前版本导入。', '',
             '## 验证', '',
             '当前 XML、切片、图片集合和哈希已检查；没有旧测试标题引用或 `_statcard.png` 图片引用。',
             '打包核验见 [UPLOAD-VALIDATION.json](UPLOAD-VALIDATION.json)，浏览器检查见 [browser-validation.json](browser-validation.json)，只读站点解析见 [site-parse-validation.json](../../vehicle-prototype/site-parse-validation.json)。',
             '未执行线上上传、导入或删除。']
    (OUT / 'DELIVERY.md').write_text('\n'.join(guide) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
