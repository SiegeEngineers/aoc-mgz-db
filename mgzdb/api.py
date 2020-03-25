"""MGZ database API."""

import time
import logging
import os
import tempfile
import zipfile

from mgzdb.add import AddFile
from mgzdb.schema import get_session, File, Match

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

    def add_series(self, zip_path, series=None, series_id=None):
        """Add a series via zip file."""
        with zipfile.ZipFile(zip_path) as series_zip:
            LOGGER.info("[%s] opened archive", os.path.basename(zip_path))
            for zip_member in series_zip.infolist():
                series_zip.extract(zip_member, path=self.temp_dir.name)
                date_time = time.mktime(zip_member.date_time + (0, 0, -1))
                os.utime(os.path.join(self.temp_dir.name, zip_member.filename), (date_time, date_time))
            for filename in sorted(series_zip.namelist()):
                if filename.endswith('/'):
                    continue
                LOGGER.info("[%s] processing member %s", os.path.basename(zip_path), filename)
                self.add_file(
                    os.path.join(self.temp_dir.name, filename),
                    os.path.basename(zip_path),
                    series,
                    series_id
                )
            LOGGER.info("[%s] finished", os.path.basename(zip_path))

    def remove(self, file_id=None, match_id=None):
        """Remove a file, match, or series.

        TODO: Use cascading deletes for this.
        """
        if file_id:
            obj = self.session.query(File).get(file_id)
            if obj:
                if len(obj.match.files) == 1:
                    obj = obj.match.files[0].match
                self.session.delete(obj)
                self.session.commit()
                return
        elif match_id:
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
                self.session.commit()
                self.session.delete(obj)
                self.session.commit()
                return
        print('not found')
