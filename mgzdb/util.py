"""Utilities."""
from datetime import datetime
from scp import SCPClient

MGZ_EXT = '.mgz'


def copy_file(handle, ssh, path):
    """Copy file to destination store."""
    handle.seek(0)
    with SCPClient(ssh.get_transport()) as scp:
        scp.putfo(handle, path)


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
