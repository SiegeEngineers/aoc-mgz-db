"""Utilities."""
import os
import re
from datetime import datetime


MGZ_EXT = '.mgz'
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


def parse_filename_timestamp(func):
    """Parse timestamp from default rec filename format."""
    if not func.startswith('rec.') or not func.endswith(MGZ_EXT) or len(func) != 23:
        return None
    return datetime(
        year=int(func[4:8]),
        month=int(func[8:10]),
        day=int(func[10:12]),
        hour=int(func[13:15]),
        minute=int(func[15:17]),
        second=int(func[17:19])
    )


def get_utc_now():
    """Get current timestamp."""
    return datetime.utcnow()
