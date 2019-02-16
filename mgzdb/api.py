"""MGZ database API."""

import csv
import logging
import multiprocessing
import os
import sys
import tempfile
import zipfile

import iso8601
import requests_cache
from sqlalchemy.exc import IntegrityError

import voobly
from mgzdb import queries
from mgzdb.add import add_file
from mgzdb.compress import decompress
from mgzdb.schema import get_session, reset, Tag, File, Match, Series
from mgzdb.util import get_store, fetch_file


LOGGER = logging.getLogger(__name__)
SOURCE_VOOBLY = 'voobly'
SOURCE_ZIP = 'zip'
SOURCE_CLI = 'cli'
SOURCE_CSV = 'csv'
SOURCE_DB = 'db'
QUERY_MATCH = 'match'
QUERY_FILE = 'file'
QUERY_SERIES = 'series'
QUERY_SUMMARY = 'summary'


class API: # pylint: disable=too-many-instance-attributes
    """MGZ Database API."""

    def __init__(self, db_path, store_host, store_path, consecutive=False, callback=None, **kwargs):
        """Initialize sessions."""

        self.session = get_session(db_path)
        self.process_args = (store_host, store_path)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = None
        self.store_host = store_host
        self.store_path = store_path
        self.db_path = db_path
        self.callback = callback
        self.consecutive = consecutive
        self.voobly = voobly.get_session(
            key=kwargs.get('voobly_key'),
            username=kwargs.get('voobly_username'),
            password=kwargs.get('voobly_password')
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
                'store': get_store(self.store_host),
                'session': get_session(self.db_path),
                'aoe2map': requests_cache.CachedSession(backend='memory'),
                'voobly': voobly.get_session(
                    key=self.voobly_key,
                    username=self.voobly_username,
                    password=self.voobly_password
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

    def add_url(self, voobly_url, download_path, tags, force=False, pov=True):
        """Add a match via Voobly url."""
        if isinstance(voobly_url, str):
            voobly_id = voobly_url.split('/')[-1]
        else:
            voobly_id = voobly_url
        try:
            match = voobly.get_match(self.voobly, voobly_id)
        except voobly.VooblyError as error:
            LOGGER.error("failed to get match: %s", error)
            return
        except ValueError:
            LOGGER.error("not an aoc match: %s", voobly_id)
            return
        players = [match['players'][0]]
        if pov:
            players = match['players']
        for player in players:
            filename = voobly.download_rec(self.voobly, player['url'], download_path)
            self.add_file(
                os.path.join(download_path, filename),
                SOURCE_VOOBLY,
                voobly_url,
                tags,
                voobly_id=voobly_id,
                played=match['timestamp'],
                force=force,
                user_data=player
            )

    def add_series(self, zip_path, tags, series=None, challonge_id=None, force=False):
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
                    SOURCE_ZIP,
                    os.path.basename(zip_path),
                    tags,
                    series,
                    challonge_id,
                    force=force
                )
            LOGGER.info("[%s] finished", os.path.basename(zip_path))

    def add_csv(self, csv_path, download_path, tags, force=False):
        """Add matches from CSV."""
        LOGGER.info("opening %s for import", csv_path)
        with open(csv_path) as csv_file:
            LOGGER.info("[%s] starting parse", os.path.basename(csv_path))
            for num, row in enumerate(csv.DictReader(csv_file)):
                LOGGER.info("[%s] adding data from row %d", os.path.basename(csv_path), num + 1)
                url = row['PlayerRecording'].replace(voobly.BASE_URL, '')
                filename = voobly.download_rec(self.voobly, url, download_path)
                old_path = os.path.join(download_path, filename)
                new_path = os.path.join(download_path, '{}.{}'.format(row['PlayerId'], filename))
                os.rename(old_path, new_path)
                self.add_file(
                    new_path,
                    SOURCE_CSV,
                    os.path.basename(csv_path),
                    tags,
                    voobly_id=row['MatchId'],
                    played=iso8601.parse_date(row['MatchDate']),
                    force=force,
                    user_data={
                        'id': row['PlayerId'],
                        'clan': None,
                        'color_id': None, # this won't work until we can set `color_id`
                        'rate_before': row['PlayerPreRating'],
                        'rate_after': row['PlayerPostRating']
                    }
                )
            LOGGER.info("[%s] finished parse", os.path.basename(csv_path))

    def add_db(self, remote, tags, force=False):
        """Add records from another database."""
        for match in remote.session.query(Match).all():
            for mgz in match.files:
                filename, data = remote.get(mgz.id)
                path = os.path.join(self.temp_dir.name, filename)
                with open(path, 'wb') as handle:
                    handle.write(data)
                series = match.series.name if match.series else None
                challonge_id = match.series.challonge_id if match.series else None
                self.add_file(
                    path,
                    SOURCE_DB,
                    mgz.id,
                    tags,
                    series,
                    challonge_id=challonge_id,
                    voobly_id=match.voobly_id,
                    played=match.played,
                    force=force,
                    user_data={
                        'id': mgz.owner.voobly_user_id,
                        'clan': mgz.owner.voobly_clan_id,
                        'color_id': mgz.owner.color_id,
                        'rate_before': mgz.owner.rate_before,
                        'rate_after': mgz.owner.rate_after
                    }
                )

    def remove(self, file_id=None, match_id=None, series_id=None):
        """Remove a file, match, or series."""
        if file_id:
            obj = self.session.query(File).get(file_id)
            if len(obj.match.files) == 1:
                obj = obj.match.files[0].match
        if match_id:
            obj = self.session.query(Match).get(match_id)
        if series_id:
            obj = self.session.query(Series).get(series_id)
        if obj:
            self.session.delete(obj)
            self.session.commit()
        else:
            print('not found')

    def tag(self, match_id, tags):
        """Tag a match."""
        match = self.session.query(Match).get(match_id)
        for tag in tags:
            try:
                obj = Tag(name=tag, match=match)
                self.session.add(obj)
                self.session.commit()
            except IntegrityError:
                self.session.rollback()

    def get(self, file_id):
        """Get a file from the store."""
        if not self.store:
            self.store = get_store(self.store_host)
        mgz_file = self.session.query(File).get(file_id)
        store_path = os.path.join(self.store_path, mgz_file.filename)
        return mgz_file.original_filename, decompress(fetch_file(self.store, store_path))

    def reset(self):
        """Reset database."""
        reset(self.db_path)
        LOGGER.info("reset database")

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
