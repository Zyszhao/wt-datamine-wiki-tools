"""Package deployable files and human installation instructions; never upload."""
import json
from zipfile import ZipFile, ZIP_DEFLATED
from paths import ROOT, WIKI, WORK

def main():
    manifest = json.loads((WIKI / 'manifest.json').read_text(encoding='utf-8'))
    files = [ROOT / p['file'] for p in manifest['pages']]
    files += [WIKI / 'uploads' / name for name in manifest['uploads']]
    files += [WIKI / name for name in ('manifest.json', 'PAGE-LIST.md', 'INSTALL.html', 'REPAIR.html', 'MULTI-TREE.html',
                                      'import-testing.xml', 'WTJTreeTesting-all-testing.xml', 'import-update.xml', 'import-tree-only.xml')]
    files += [ROOT / 'docs' / name for name in ('DEPLOYMENT.md', 'UPDATE.md',
                                               'CLASSIFICATION-AND-VISIBILITY.md','MULTI-TREE.md','LAYOUT-AND-IMPORT.md')]
    if len(files) != len(set(files)):
        raise ValueError('Duplicate package entry')
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    target = WORK / 'packages' / 'WTJTreeTesting-deploy.zip'
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(target)

if __name__ == '__main__':
    main()
