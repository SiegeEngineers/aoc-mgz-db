"""MGZ database API."""

import time
import logging
import os
import tempfile
import zipfile
from datetime import datetime

import rarfile

from mgzdb.add import AddFile
from mgzdb.util import parse_filename
from mgzdb.schema import (
    get_session,
    ObjectInstance, Market, Timeseries, Research, get_session, Match, File,
    Chat, ActionLog, Transaction, Tribute, Formation
)

LOGGER = logging.getLogger(__name__)


class API: # pylint: disable=too-many-instance-attributes
    """MGZ Database API."""

    def __init__(self, db_path, store_path, platforms, playback=None):
        """Initialize sessions."""
        self.session, self.engine = get_session(db_path)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = store_path
        self.platforms = platforms
        self.playback = playback
        self.adder = AddFile(self.session, self.platforms, self.store_path, playback)
        LOGGER.info("connected to database @ %s", db_path)

    def has_match(self, platform_id, match_id):
        """Check if a platform match exists."""
        return self.session.query(Match).filter_by(platform_id=platform_id, platform_match_id=match_id).one_or_none() is not None

    def add_file(self, *args, **kwargs):
        """Add file."""
        LOGGER.info("processing file %s", args[0])
        return self.adder.add_file(*args, **kwargs)

    def add_match(self, platform, url, single_pov=True):
        """Add a match via platform url."""
        if isinstance(url, str):
            match_id = url.split('/')[-1]
        else:
            match_id = url
        try:
            match = self.platforms[platform].get_match(match_id)
        except RuntimeError as error:
            LOGGER.error("failed to get match: %s", error)
            return
        except ValueError:
            LOGGER.error("not an aoc match: %s", match_id)
            return
        players = match['players']
        chose = None
        if single_pov:
            for player in players:
                if player['url']:
                    chose = player
                    break
            if not chose:
                return
            players = [chose]
        for player in players:
            if not player['url']:
                continue
            try:
                filename = self.platforms[platform].download_rec(player['url'], self.temp_dir.name)
            except RuntimeError:
                LOGGER.error("could not download valid rec: %s", match_id)
                continue
            self.add_file(
                os.path.join(self.temp_dir.name, filename),
                url,
                platform_id=platform,
                platform_match_id=match_id,
                platform_metadata=match.get('metadata'),
                played=match['timestamp'],
                ladder=match.get('ladder'),
                user_data=match['players']
            )

    def add_series(self, archive_path, series=None, series_id=None):
        """Add a series via zip file."""
        try:
            if archive_path.endswith('zip'):
                compressed = zipfile.ZipFile(archive_path)
            elif archive_path.endswith('rar'):
                compressed = rarfile.RarFile(archive_path)
            else:
                LOGGER.error("[%s] not a valid archive", os.path.basename(archive_path))
                return
        except zipfile.BadZipFile:
            LOGGER.error("[%s] bad zip file", os.path.basename(archive_path))
            return
        with compressed as series_zip:
            LOGGER.info("[%s] opened archive", os.path.basename(archive_path))
            for zip_member in series_zip.infolist():
                series_zip.extract(zip_member, path=self.temp_dir.name)
                date_time = time.mktime(zip_member.date_time + (0, 0, -1))
                os.utime(os.path.join(self.temp_dir.name, zip_member.filename), (date_time, date_time))
            for filename in sorted(series_zip.namelist()):
                if filename.endswith('/'):
                    continue
                LOGGER.info("[%s] processing member %s", os.path.basename(archive_path), filename)
                played, _ = parse_filename(os.path.basename(filename))
                if not played:
                    played = datetime.fromtimestamp(os.path.getmtime(os.path.join(self.temp_dir.name, filename)))
                self.add_file(
                    os.path.join(self.temp_dir.name, filename),
                    os.path.basename(archive_path),
                    series,
                    series_id,
                    played=played
                )
            LOGGER.info("[%s] finished", os.path.basename(archive_path))

    def add_zip(self, platform_id, archive_path):
        """Add matches via zip file."""
        guess = platform_id == 'auto'
        try:
            if archive_path.endswith('zip'):
                compressed = zipfile.ZipFile(archive_path)
            elif archive_path.endswith('rar'):
                compressed = rarfile.RarFile(archive_path)
            else:
                LOGGER.error("[%s] not a valid archive", os.path.basename(archive_path))
                return
        except zipfile.BadZipFile:
            LOGGER.error("[%s] bad zip file", os.path.basename(archive_path))
            return
        with compressed as series_zip:
            LOGGER.info("[%s] opened archive", os.path.basename(archive_path))
            for compressed_file in compressed.infolist():
                try:
                    series_zip.extract(compressed_file, path=self.temp_dir.name)
                    date_time = time.mktime(compressed_file.date_time + (0, 0, -1))
                    os.utime(os.path.join(self.temp_dir.name, compressed_file.filename), (date_time, date_time))
                except (zipfile.BadZipFile, rarfile.Error):
                    LOGGER.error("Failed to extract file")
                    return
            for filename in sorted(compressed.namelist()):
                if filename.endswith('/'):
                    continue
                if not (filename.endswith('.mgz') or filename.endswith('.mgx') or filename.endswith('.mgl') or filename.endswith('.aoe2record')):
                    continue
                LOGGER.info("[%s] processing member %s", os.path.basename(archive_path), filename)
                played, _ = parse_filename(os.path.basename(filename))
                if not played:
                    played = datetime.fromtimestamp(os.path.getmtime(os.path.join(self.temp_dir.name, filename)))
                if guess and played:
                    if played >= datetime(2009, 9, 17):
                        platform_id = 'voobly'
                    elif played < datetime(2009, 9, 17) and played >= datetime(2007, 9, 20):
                        platform_id = 'igz'
                    elif played < datetime(2007, 9, 20) and played >= datetime(2006, 8, 1):
                        platform_id = 'gamepark'
                    elif played < datetime(2006, 8, 1):
                        platform_id = 'zone'
                    else:
                        platform_id = None
                elif guess and not played:
                    platform_id = None
                self.add_file(
                    os.path.join(self.temp_dir.name, filename),
                    os.path.basename(archive_path),
                    platform_id=platform_id,
                    played=played
                )
            LOGGER.info("[%s] finished", os.path.basename(archive_path))

    def remove(self, file_id=None, match_id=None):
        """Remove a file, match, or series.

        TODO: Use cascading deletes for this.
        """
        if file_id:
            obj = self.session.query(File).get(file_id)
            self.session.delete(obj)
            self.session.commit()
            return
        if match_id:
            obj = self.session.query(Match).get(match_id)
            if obj:
                for mgz in obj.files:
                    self.session.delete(mgz)
                self.session.commit()
                with self.session.no_autoflush:
                    for team in obj.teams:
                        self.session.delete(team)
                    for player in obj.players:
                        self.session.delete(player)
                self.session.query(ObjectInstance).filter(ObjectInstance.match_id==match_id).delete()
                self.session.query(Market).filter(Market.match_id==match_id).delete()
                self.session.query(Timeseries).filter(Timeseries.match_id==match_id).delete()
                self.session.query(Research).filter(Research.match_id==match_id).delete()
                self.session.query(Chat).filter(Chat.match_id==match_id).delete()
                self.session.query(ActionLog).filter(ActionLog.match_id==match_id).delete()
                self.session.query(Tribute).filter(Tribute.match_id==match_id).delete()
                self.session.query(Transaction).filter(Transaction.match_id==match_id).delete()
                self.session.query(Formation).filter(Formation.match_id==match_id).delete()
                self.session.commit()
                self.session.delete(obj)
                self.session.commit()
                return
        print('not found')
