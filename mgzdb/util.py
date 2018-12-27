"""Utilities."""
import os
import tempfile
import re
from datetime import datetime
from scp import SCPClient


MGZ_EXT = '.mgz'
ZIP_EXT = '.zip'
CHALLONGE_ID_LENGTH = 9


def copy_file(handle, ssh, path):
    """Copy file to destination store."""
    handle.seek(0)
    with SCPClient(ssh.get_transport()) as scp:
        scp.putfo(handle, path)


def fetch_file(ssh, path):
    """Fetch file from destination store."""
    with tempfile.NamedTemporaryFile() as temp:
        with SCPClient(ssh.get_transport()) as scp:
            scp.get(path, local_path=temp.name)
        temp.flush()
        with open(temp.name, 'rb') as handle:
            return handle.read()


def parse_series_path(path):
    """Parse series name and challonge ID from path."""
    filename = os.path.basename(path)
    start = 0
    challonge_id = None
    pattern = re.compile('[0-9]{' + str(CHALLONGE_ID_LENGTH) + '}')
    if pattern.match(filename):
        challonge_id = int(filename[:CHALLONGE_ID_LENGTH])
        start = CHALLONGE_ID_LENGTH + 1
    series = filename[start:].replace(ZIP_EXT, '')
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
