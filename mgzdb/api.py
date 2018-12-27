"""MGZ database API."""

import csv
import hashlib
import io
import logging
import lzma
import os
import tempfile
import zipfile
from datetime import timedelta

import iso8601
import pkg_resources
import requests_cache
from paramiko import SSHClient
from sqlalchemy.orm.exc import NoResultFound

import mgz.const
import mgz.summary
import voobly

from mgzdb.schema import (
    get_session, Match, VooblyUser, Tag, Series, File, Source,
    Mod, VooblyLadder, Player, Civilization, Map, VooblyClan, Team
)
from mgzdb.util import copy_file, fetch_file, parse_filename_timestamp
from mgzdb import queries


LOGGER = logging.getLogger(__name__)
SOURCE_VOOBLY = 'voobly'
SOURCE_ZIP = 'zip'
SOURCE_CLI = 'cli'
SOURCE_CSV = 'csv'
QUERY_MATCH = 'match'
QUERY_FILE = 'file'
QUERY_SERIES = 'series'
QUERY_SUMMARY = 'summary'
LOG_ID_LENGTH = 8
COMPRESSED_EXT = '.xz'
MAP_URL = 'https://aoe2map.net/api/rms/file'


class API:
    """MGZ Database API."""

    def __init__(self, db_path, store_host, store_path, voobly_key, voobly_username, voobly_password):
        """Initialize sessions."""
        ssh = SSHClient()
        ssh.load_system_host_keys()
        ssh.connect(store_host)
        self.store = ssh
        self.store_host = store_host
        self.store_path = store_path
        self.session = get_session(db_path)
        self.aoe2map = requests_cache.CachedSession()
        self.voobly = voobly.get_session(
            key=voobly_key,
            username=voobly_username,
            password=voobly_password
        )

    def add_url(self, voobly_url, download_path, tags, force=False):
        """Add a match via Voobly url."""
        voobly_id = voobly_url.split('/')[-1]
        try:
            match = voobly.get_match(self.voobly, voobly_id)
        except voobly.VooblyError as error:
            LOGGER.error("failed to get match: %s", error)
            return
        for player in match['players']:
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
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_path) as series_zip:
                LOGGER.info("[%s] opened archive", os.path.basename(zip_path))
                series_zip.extractall(temp_dir)
                for filename in sorted(series_zip.namelist()):
                    if filename.endswith('/'):
                        continue
                    LOGGER.info("[%s] processing member file %s", os.path.basename(zip_path), filename)
                    self.add_file(
                        os.path.join(temp_dir, filename),
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
                        'username': row['PlayerName'],
                        'clan': None,
                        'color_id': None, # this won't work until we can set `color_id`
                        'rate_before': row['PlayerPreRating'],
                        'rate_after': row['PlayerPostRating']
                    }
                )
            LOGGER.info("[%s] finished parse", os.path.basename(csv_path))

    def add_file(
            self, rec_path, source, reference, tags, series=None, challonge_id=None,
            voobly_id=None, played=None, force=False, user_data=None
    ):
        """Add a single mgz file."""

        if not os.path.isfile(rec_path):
            LOGGER.error("%s is not a file", rec_path)
            return False

        original_filename = os.path.basename(rec_path)

        with open(rec_path, 'rb') as handle:
            data = handle.read()

        file_hash = hashlib.sha1(data).hexdigest()
        log_id = file_hash[:LOG_ID_LENGTH]
        LOGGER.info("[f:%s] add started", log_id)

        if self.session.query(File).filter_by(hash=file_hash).count() > 0:
            LOGGER.warning("[f:%s] file already exists", log_id)
            return False

        try:
            handle = io.BytesIO(data)
            summary = mgz.summary.Summary(handle, len(data))
        except RuntimeError:
            LOGGER.error("[f:%s] invalid mgz file", log_id)
            return False

        compressed_filename = '{}{}'.format(file_hash, COMPRESSED_EXT)
        LOGGER.info("[f:%s] compressing %s as %s", log_id, os.path.basename(rec_path), compressed_filename)
        new_path = os.path.join(self.store_path, compressed_filename)
        LOGGER.info("[f:%s] copying to %s:%s", log_id, self.store_host, new_path)
        copy_file(io.BytesIO(lzma.compress(data)), self.store, new_path)

        match_hash = summary.get_hash()
        try:
            match = self.session.query(Match).filter_by(hash=match_hash).one()
            LOGGER.info("[f:%s] match already exists; appending", log_id)
        except NoResultFound:
            LOGGER.info("[f:%s] adding match", log_id)
            if not played:
                played = parse_filename_timestamp(original_filename)
            match = self._add_match(summary, played, tags, match_hash, series, challonge_id, voobly_id, force)
            if not match:
                return False

        self._update_match_user(match.id, user_data)

        new_file = File(
            filename=compressed_filename,
            original_filename=original_filename,
            hash=file_hash,
            size=summary.size,
            reference=reference,
            match=match,
            source=self._get_unique(Source, name=source),
            owner_number=summary.get_owner(),
            parser_version=pkg_resources.get_distribution('mgz').version
        )
        self.session.add(new_file)
        self.session.commit()
        LOGGER.info("[f:%s] add finished, file id: %d, match id: %d", log_id, new_file.id, match.id)
        return True

    def _add_match(self, summary, played, tags, match_hash, series=None, challonge_id=None, voobly_id=None, force=False):
        postgame = summary.get_postgame()
        duration = summary.get_duration()
        from_voobly, ladder = summary.get_ladder()
        settings = summary.get_settings()
        map_name, map_size = summary.get_map()
        map_uuid = None
        completed = postgame.complete if postgame else False
        restored, _ = summary.get_restored()
        postgame = postgame is not None
        major_version, minor_version = summary.get_version()
        mod_name, mod_version = summary.get_mod()
        teams = summary.get_teams()
        diplomacy = summary.get_diplomacy()
        log_id = match_hash[:LOG_ID_LENGTH]

        flagged = False
        if restored:
            LOGGER.warning("[m:%s] is restored game", log_id)
            flagged = True

        if not completed:
            LOGGER.warning("[m:%s] was not completed", log_id)
            flagged = True

        if flagged:
            if not force:
                LOGGER.error("[m:%s] skipping add", log_id)
                return False
            LOGGER.warning("[m:%s] adding it anyway", log_id)

        resp = self.aoe2map.get('{}/{}.rms'.format(MAP_URL, map_name)).json()
        if resp['maps']:
            map_uuid = resp['maps'][0]['uuid']

        match = self._get_unique(
            Match, ['hash', 'voobly_id'],
            voobly_id=voobly_id,
            played=played,
            hash=match_hash,
            series=self._get_unique(Series, name=series, challonge_id=challonge_id),
            version=major_version,
            minor_version=minor_version,
            mod_version=mod_version,
            mod=self._get_unique(Mod, name=mod_name),
            voobly=from_voobly,
            voobly_ladder=self._get_unique(VooblyLadder, name=ladder),
            map=self._get_unique(Map, name=map_name, uuid=map_uuid),
            map_size=map_size,
            duration=timedelta(milliseconds=duration),
            completed=completed,
            restored=restored,
            postgame=postgame,
            type=settings['type'],
            difficulty=settings['difficulty'],
            population_limit=settings['population_limit'],
            reveal_map=settings['reveal_map'],
            speed=settings['speed'],
            cheats=settings['cheats'],
            lock_teams=settings['lock_teams'],
            diplomacy_type=diplomacy['type'],
            team_size=diplomacy.get('team_size')
        )

        winning_team_id = None
        for data in summary.get_players():
            team_id = None
            for i, team in enumerate(teams):
                if data['number'] in team:
                    team_id = i
            if data['winner']:
                winning_team_id = team_id
            player = Player(
                civilization=self._get_unique(
                    Civilization,
                    name=mgz.const.CIVILIZATION_NAMES[data['civilization']]
                ),
                team=self._get_unique(
                    Team,
                    ['match', 'team_id'],
                    match=match,
                    team_id=team_id
                ),
                human=data['human'],
                name=data['name'],
                number=data['number'],
                color_id=data['color_id'],
                winner=data['winner'],
                mvp=data['mvp'],
                score=data['score']
            )
            if match.voobly:
                self._guess_match_user(player, data['name'])
            match.players.append(player)

        if tags:
            self._add_tags(match, tags)
        match.winning_team_id = winning_team_id
        return match

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
        self.session.delete(obj)
        self.session.commit()

    def tag(self, match_id, tags):
        """Tag a match."""
        match = self.session.query(Match).get(match_id)
        self._add_tags(match, tags)

    def get(self, file_id):
        """Get a file from the store."""
        mgz_file = self.session.query(File).get(file_id)
        store_path = os.path.join(self.store_path, mgz_file.filename)
        return mgz_file.original_filename, lzma.decompress(fetch_file(self.store, store_path))

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

    def _add_tags(self, match, tags):
        """Add tags to a match."""
        for tag in tags:
            self._get_unique(Tag, name=tag, match=match)

    def _update_match_user(self, match_id, user_data):
        """Update Voobly User info on Match."""
        if user_data:
            player = self.session.query(Player).filter_by(match_id=match_id, color_id=user_data['color_id']).one()
            LOGGER.info("[m:%s] updating voobly user data", player.match.hash[:LOG_ID_LENGTH])
            player.voobly_user_id = user_data['id']
            player.voobly_clan = self._get_unique(VooblyClan, ['id'], id=user_data['clan'])
            player.rate_before = user_data['rate_before']
            player.rate_after = user_data['rate_after']

    def _guess_match_user(self, player, name):
        """Guess Voobly User from a player name."""
        try:
            player.voobly_user = self._get_unique(VooblyUser, ['id'], id=voobly.find_user(self.voobly, name))
            clan = name.split(']')[0][1:] if name.find(']') > 0 else None
            player.voobly_clan = self._get_unique(VooblyClan, ['id'], id=clan)
        except voobly.VooblyError as error:
            LOGGER.warning("failed to lookup Voobly user: %s", error)

    def _get_unique(self, table, keys=None, **kwargs):
        """Get unique object either by query or creation."""
        if not keys:
            keys = ['name']
        if not any([kwargs[k] is not None for k in keys]):
            return None
        try:
            return self.session.query(table).filter_by(**{k:kwargs[k] for k in keys}).one()
        except NoResultFound:
            obj = table(**kwargs)
            self.session.add(obj)
            self.session.commit()
            return obj
