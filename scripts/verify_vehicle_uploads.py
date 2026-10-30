"""Verify the delivered XML/images against the upload list and read-only audits."""
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from paths import WIKI, IMPORT_PACK, WORK


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def pages(path):
    ns={'m':'http://www.mediawiki.org/xml/export-0.11/'}
    result={}
    for p in ET.parse(path).findall('m:page',ns):
        title=p.findtext('m:title',namespaces=ns)
        assert title not in result
        result[title]=(p.findtext('m:revision/m:model',namespaces=ns),p.findtext('m:revision/m:text',namespaces=ns))
    return result


def main():
    assert (IMPORT_PACK / 'Full/WTJ-vehicle-pages.xml').is_file(), 'Only the current formal vehicle package is accepted; old demo packages are retired'
    return verify_formal()



def verify_formal():
    from asset_naming import vehicle_image_name
    from audit_game_images import wiki_key
    folder = WIKI / 'production/vehicle-pages'
    manifest = read(folder / 'manifest.json')
    full = pages(IMPORT_PACK / 'Full/WTJ-vehicle-pages.xml')
    slices = {}
    for path in (IMPORT_PACK / 'Slices').glob('*.xml'):
        part = pages(path)
        assert not set(part) & set(slices)
        slices.update(part)
    assert full == slices and len(full) == manifest['pages']
    assert not any(re.search(r'Testing|Demo2026', title + content) for title, (_, content) in full.items())
    assert all(code in full for code in manifest['articles'])
    assert not any(title.endswith(('/basic-info', '/player-content')) for title in full)
    for code in manifest['articles']:
        data = json.loads(full['WTJ/data/vehicle/' + code + '.json'][1])
        assert wiki_key(data['image_file']) == wiki_key(vehicle_image_name(code + '.png', large=True))
        assert code + '/basic-info' in full['模块:WTJ/vehicle-content'][1].replace("id..", "'" + code + "'..") or "local title=id..'/'..kind" in full['模块:WTJ/vehicle-content'][1]
    for relative, expected in manifest['xml_files'].items():
        assert hashlib.sha256((IMPORT_PACK / relative).read_bytes()).hexdigest() == expected
    image_report = read(WIKI / 'production/game-image-audit/manifest.json')
    delivery = read(WIKI / 'production/game-image-audit/DELIVERY.json')
    evidence = read(WIKI / 'production/game-image-audit/site-evidence.json')['targets']
    by_name = {a['filename']: a for a in image_report['assets']}
    files = [p for p in IMPORT_PACK.rglob('*') if p.is_file() and p.suffix in ('.png', '.svg')]
    assert len({wiki_key(p.name) for p in files}) == len(files)
    assert not any('Testing' in p.name or '_statcard.png' in p.name for p in files)
    expected_supplemental = set(delivery['files'])
    assert {p.relative_to(IMPORT_PACK / 'SupplementalImages').as_posix() for p in (IMPORT_PACK / 'SupplementalImages').rglob('*') if p.is_file()} == expected_supplemental
    root_names = {p.name for p in IMPORT_PACK.glob('*') if p.is_file()}
    assert root_names == set(manifest['missing_images'])
    for path in files:
        item = by_name[path.name]
        assert item['status'] == 'missing'
        assert all(evidence[t]['status'] != 'unknown' and not evidence[t].get('record', {}).get('imageinfo') for t in item['titles'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() in {s['sha256'] for s in item['sources']}
    assert {p.name for p in files} == {a['filename'] for a in image_report['assets'] if a['status'] == 'missing'}
    result = {'passed': True, 'pages': len(full), 'articles': manifest['articles'], 'images': len(files),
              'no_test_titles_or_references': True, 'xml_hashes_and_slices': True,
              'statcard_suffix': '_资料卡', 'image_names_unique': True, 'image_original_bytes': True,
              'missing_image_evidence': True, 'live_wiki_written': False}
    (folder / 'UPLOAD-VALIDATION.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__=='__main__':
    main()
