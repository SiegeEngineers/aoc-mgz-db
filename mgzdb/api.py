"""MGZ database API."""

import logging
import multiprocessing
import json
import os
import sys
import tempfile
import zipfile

import iso8601
import requests_cache

import voobly
from mgzdb import platforms
from mgzdb.add import add_file
from mgzdb.compress import decompress
from mgzdb.schema import get_session, File, Match
from mgzdb.util import get_file


LOGGER = logging.getLogger(__name__)


class API: # pylint: disable=too-many-instance-attributes
    """MGZ Database API."""

    def __init__(self, db_path, store_path, consecutive=False, callback=None, **kwargs):
        """Initialize sessions."""

        self.session, _ = get_session(db_path)
        self.process_args = (store_path,)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = None
        self.store_path = store_path
        self.db_path = db_path
        self.callback = callback
        self.debug = None
        self.consecutive = consecutive
        self.platforms = platforms.factory(
            voobly_key=kwargs.get('voobly_key'),
            voobly_username=kwargs.get('voobly_username'),
            voobly_password=kwargs.get('voobly_password')
        )
        self.voobly_key = kwargs.get('voobly_key')
        self.voobly_username = kwargs.get('voobly_username')
        self.voobly_password = kwargs.get('voobly_password')
        self.playback = kwargs.get('playback', [])
        self.pool = None
        self.total = 0
        LOGGER.info("connected to database @ %s", db_path)

    def start(self):
        """Start child processes."""
        playback_queue = multiprocessing.Queue()
        for p in self.playback:
            playback_queue.put(p)
        def init_worker(function):
            playback = playback_queue.get(True)
            LOGGER.info('%s', playback)
            function.connections = {
                'session': get_session(self.db_path)[0],
                'aoe2map': requests_cache.CachedSession(backend='memory'),
                'platforms': platforms.factory(
                    voobly_key=self.voobly_key,
                    voobly_username=self.voobly_username,
                    voobly_password=self.voobly_password
                ),
                'playback': playback
            }
        if self.consecutive:
            init_worker(add_file)
            self.debug = add_file
        else:
            LOGGER.info("starting pool with %d workers", len(self.playback))
            self.pool = multiprocessing.Pool(
                processes=len(self.playback),
                initializer=init_worker,
                initargs=(add_file,)
            )

    def finished(self):
        """Wait for child processes to end."""
        try:
            if not self.consecutive:
                self.pool.close()
                self.pool.join()
        except KeyboardInterrupt:
            print('user requested exit')
            sys.exit()
        finally:
            self.temp_dir.cleanup()

    def add_file(self, *args, **kwargs):
        """Add file via process pool."""
        self.total += 1
        LOGGER.info("processing file %s", args[0])
        if self.consecutive:
            self.debug(*self.process_args, *args, **kwargs)
        else:
            if not self.pool:
                raise ValueError('call start() first')
            self.pool.apply_async(
                add_file,
                args=(*self.process_args, *args),
                kwds=kwargs,
                callback=self._file_added,
                error_callback=self._critical_error
            )

    def add_match(self, platform, url, single_pov=False):
        """Add a match via platform url."""
        if isinstance(url, str):
            match_id = url.split('/')[-1]
        else:
            match_id = url
        try:
            match = self.platforms[platform].get_match(match_id)
        except voobly.VooblyError as error:
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
                played=match['timestamp'],
                ladder=match.get('ladder'),
                user_data=match['players']
            )

    def add_series(self, zip_path, series=None, series_id=None):
        """Add a series via zip file."""
        with zipfile.ZipFile(zip_path) as series_zip:
            LOGGER.info("[%s] opened archive", os.path.basename(zip_path))
            series_zip.extractall(self.temp_dir.name)
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
        """Remove a file, match, or series."""
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

    def get(self, file_id):
        """Get a file from the store."""
        mgz_file = self.session.query(File).get(file_id)
        return mgz_file.original_filename, decompress(get_file(self.store_path, mgz_file.filename))

    def _file_added(self, success): # pylint: disable=unused-argument
        """Callback when file is addded."""
        if self.callback:
            self.callback()

    def _critical_error(self, val): # pylint: disable=unused-argument
        """Handle critical errors from child processes."""
        print(val, type(val))
        if self.callback:
            self.callback()
