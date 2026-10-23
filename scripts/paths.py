"""Shared offline project paths; never depend on the caller's working directory."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get('WTW_DATAMINE', str(ROOT.parent / 'War-Thunder-Datamine'))).resolve()
WIKI = ROOT / 'wiki'
WORK = ROOT / 'work'
VENDOR = ROOT / 'vendor/python/packages'
SCRIPT_USER = os.environ.get('WTW_SCRIPT_USER', '319206634')

def ensure_output_dirs():
    for directory in (WIKI / 'pages', WIKI / 'uploads', WORK / 'assets',
                      WORK / 'preview', WORK / 'reports', WORK / 'exports'):
        directory.mkdir(parents=True, exist_ok=True)
