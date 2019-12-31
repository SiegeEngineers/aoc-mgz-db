"""Utilities."""
import os
import re
from datetime import datetime


MGZ_EXT = '.mgz'
DE_EXT = '.aoe2record'
ZIP_EXT = '.zip'
CHALLONGE_ID_LENGTH = 9
COLLAPSE_WHITESPACE = re.compile(r'\W+')
REMOVE_STRINGS = ['(POV)', '(PoV)', 'PoV']
PATH_DEPTH = 3
PATH_SIZE = 2


def path_components(filename):
    """Compute components of path."""
    components = []
    for i in range(0, PATH_DEPTH):
        components.append(filename[i * PATH_SIZE : (i * PATH_SIZE) + PATH_SIZE])
    return components


def save_file(data, path, filename):
    """Save file to store."""
    path = os.path.abspath(os.path.expanduser(path))
    components = path_components(filename)
    new_path = os.path.join(path, *components)
    os.makedirs(new_path, exist_ok=True)
    destination = os.path.join(new_path, filename)
    with open(destination, 'wb') as handle:
        handle.write(data)
    return destination


def get_file(path, filename):
    """Get file handle from store."""
    path = os.path.abspath(os.path.expanduser(path))
    components = path_components(filename)
    return open(os.path.join(os.path.join(path, *components), filename), 'rb')


def parse_series_path(path):
    """Parse series name and challonge ID from path."""
    filename = os.path.basename(path)
    start = 0
    challonge_id = None
    challonge_pattern = re.compile('[0-9]+')
    challonge = challonge_pattern.match(filename)
    if challonge:
        challonge_id = filename[:challonge.end()]
        start = challonge.end() + 1
    manual_pattern = re.compile(r'.+?\-[0-9]+\-[0-9]+')
    manual = manual_pattern.match(filename)
    if manual:
        challonge_id = filename[manual.start():manual.end()]
        start = manual.end() + 1
    series = filename[start:].replace(ZIP_EXT, '')
    for remove in REMOVE_STRINGS:
        series = series.replace(remove, '')
    series = COLLAPSE_WHITESPACE.sub(' ', series).strip()
    return series, challonge_id


def parse_filename(filename):
    mgz = parse_filename_mgz(filename)
    de = parse_filename_de(filename)
    if mgz[0]:
        return mgz
    elif de[0]:
        return de
    return None, None


def parse_filename_de(filename):
    if not filename.startswith('MP Replay') or not filename.endswith(DE_EXT) or len(filename) < 45:
        return None, None
    return datetime(
        year=int(filename[28:32]),
        month=int(filename[33:35]),
        day=int(filename[36:38]),
        hour=int(filename[39:41]),
        minute=int(filename[41:43]),
        second=int(filename[43:45])
        ), filename[11:26]


def parse_filename_mgz(filename):
    """Parse timestamp from default rec filename format."""
    if not filename.startswith('rec.') or not filename.endswith(MGZ_EXT) or len(filename) != 23:
        return None, None
    return datetime(
        year=int(filename[4:8]),
        month=int(filename[8:10]),
        day=int(filename[10:12]),
        hour=int(filename[13:15]),
        minute=int(filename[15:17]),
        second=int(filename[17:19])
    ), None


def get_utc_now():
    """Get current timestamp."""
    return datetime.utcnow()
