"""Site-wide image names. Small cards retain source names; large cards add a suffix."""
import re
from pathlib import Path

STATCARD_SUFFIX = '_资料卡'


def mediawiki_file_key(filename):
    """MediaWiki first-letter case and underscore/space equivalence only."""
    name = ' '.join(filename.replace('_', ' ').split())
    return name[:1].upper() + name[1:]


def vehicle_image_name(filename, *, large=False):
    name = Path(filename).name
    if name != filename or not re.fullmatch(r'[A-Za-z0-9_.-]+\.png', name):
        raise ValueError('Invalid vehicle image filename: ' + str(filename))
    return Path(name).stem + STATCARD_SUFFIX + '.png' if large else name


def bind_namespace(source, namespace):
    return (source.replace('WTJTreeTesting', namespace).replace('WTJ/', namespace + '/')
            .replace('WTJ-vehicle', namespace + '-vehicle')
            .replace("local prefix='WTJ'", "local prefix='" + namespace + "'"))
