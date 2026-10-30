"""Shared offline project paths; never depend on the caller's working directory."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get('WTW_DATAMINE', str(ROOT.parent / 'War-Thunder-Datamine'))).resolve()
WIKI = ROOT / 'wiki'
WORK = ROOT / 'work'
VENDOR = ROOT / 'vendor/python/packages'
SCRIPT_USER = os.environ.get('WTW_SCRIPT_USER', '319206634')
IMPORT_PACK = ROOT.parent / 'ImportPack'

def reset_import_pack():
    """Clear only the agreed delivery directory, after checking its absolute path."""
    import shutil
    expected = ROOT.parent.resolve() / 'ImportPack'
    if IMPORT_PACK.is_symlink() or IMPORT_PACK.resolve() != expected:
        raise ValueError('Unsafe import output path: '+str(IMPORT_PACK))
    IMPORT_PACK.mkdir(exist_ok=True)
    for path in IMPORT_PACK.iterdir():
        if path.is_symlink(): path.unlink()
        elif path.is_dir(): shutil.rmtree(path)
        else: path.unlink()
    return IMPORT_PACK

def ensure_output_dirs():
    for directory in (WIKI / 'pages', WIKI / 'uploads', WORK / 'assets',
                      WORK / 'preview', WORK / 'reports', WORK / 'exports'):
        directory.mkdir(parents=True, exist_ok=True)
