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
from mgzdb import queries, platforms
from mgzdb.add import add_file
from mgzdb.compress import decompress
from mgzdb.schema import get_session, reset, File, Match
from mgzdb.util import get_file


LOGGER = logging.getLogger(__name__)
QUERY_MATCH = 'match'
QUERY_FILE = 'file'
QUERY_SERIES = 'series'
QUERY_SUMMARY = 'summary'


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
        self.pool = None
        self.total = 0
        LOGGER.info("connected to database @ %s", db_path)

    def start(self):
        """Start child processes."""
        def init_worker(function):
            function.connections = {
                'session': get_session(self.db_path)[0],
                'aoe2map': requests_cache.CachedSession(backend='memory'),
                'platforms': platforms.factory(
                    voobly_key=self.voobly_key,
                    voobly_username=self.voobly_username,
                    voobly_password=self.voobly_password
                )
            }
        if self.consecutive:
            init_worker(add_file)
            self.debug = add_file
        else:
            self.pool = multiprocessing.Pool(
                initializer=init_worker,
                initargs=(add_file, )
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
                LOGGER.info("[%s] processing member file %s", os.path.basename(zip_path), filename)
                self.add_file(
                    os.path.join(self.temp_dir.name, filename),
                    os.path.basename(zip_path),
                    series,
                    series_id
                )
            LOGGER.info("[%s] finished", os.path.basename(zip_path))

    def add_db(self, remote):
        """Add records from another database."""
        for match in remote.session.query(Match).all():
            for mgz in match.files:
                filename, data = remote.get(mgz.id)
                path = os.path.join(self.temp_dir.name, filename)
                with open(path, 'wb') as handle:
                    handle.write(data)
                series = match.series.name if match.series else None
                series_id = match.series.series_id if match.series else None
                self.add_file(
                    path,
                    mgz.id,
                    series,
                    series_id=series_id,
                    platform_id=match.platform_id,
                    platform_match_id=match.platform_match_id,
                    played=match.played,
                    ladder=match.ladder.name if match.ladder else None,
                    user_data=[{
                        'id': mgz.owner.voobly_user_id,
                        'clan': mgz.owner.voobly_clan_id,
                        'color_id': mgz.owner.color_id,
                        'rate_before': mgz.owner.rate_before,
                        'rate_after': mgz.owner.rate_after
                    }]
                )

    def add_archive(self, path, single_pov=False):
        """Add records from archive."""
        archive_path = os.path.abspath(os.path.expanduser(path))
        for platform in os.listdir(archive_path):
            LOGGER.info("[%s] starting platform", platform)
            for subdir in os.listdir(os.path.join(archive_path, platform)):
                for match_id in os.listdir(os.path.join(archive_path, platform, subdir)):
                    match_path = os.path.join(archive_path, platform, subdir, match_id)
                    if not os.path.exists(os.path.join(match_path, 'metadata.json')):
                        continue
                    for zipped in os.listdir(match_path):
                        if zipped.endswith('.zip'):
                            with zipfile.ZipFile(os.path.join(match_path, zipped), 'r') as zip_ref:
                                zip_ref.extractall(os.path.join(self.temp_dir.name, match_id))
                    for mgz in os.listdir(os.path.join(self.temp_dir.name, match_id)):
                        if not mgz.endswith('.mgz'):
                            continue
                        mgz_path = os.path.join(self.temp_dir.name, match_id, mgz)
                        LOGGER.info('[%s][%s] adding match: %s', platform, match_id, mgz_path)
                        match = json.loads(open(os.path.join(match_path, 'metadata.json'), 'r').read())
                        self.add_file(
                            mgz_path,
                            mgz,
                            None, # series
                            platform_id=platform,
                            platform_match_id=int(match_id),
                            ladder=match.get('ladder'),
                            played=iso8601.parse_date(match['timestamp']),
                            user_data=match['players']
                        )
                        if single_pov:
                            break

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

    def reset(self):
        """Reset database."""
        reset(self.db_path)
        LOGGER.info("reset database")

    def search(self):
        """Search database."""
        return self.session.query(Match).all()

    def query(self, query_type, **kwargs):
        """Query database."""
        if query_type == QUERY_MATCH:
            return queries.get_match(self.session, kwargs['match_id'])
        if query_type == QUERY_FILE:
            return queries.get_file(self.session, kwargs['file_id'])
        if query_type == QUERY_SERIES:
            return queries.get_series(self.session, kwargs['series_id'])
        if query_type == QUERY_SUMMARY:
            return queries.get_summary(self.session)
        raise ValueError('unsupported query type')

    def _file_added(self, success): # pylint: disable=unused-argument
        """Callback when file is addded."""
        if self.callback:
            self.callback()

    def _critical_error(self, val): # pylint: disable=unused-argument
        """Handle critical errors from child processes."""
        print(val, type(val))
        if self.callback:
            self.callback()
