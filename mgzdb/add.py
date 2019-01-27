"""MGZ database API."""

import hashlib
import io
import logging
import os
import sys
from datetime import timedelta

import pkg_resources
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError

import mgz.const
import mgz.summary
import voobly

from mgzdb.schema import (
    Match, VooblyUser, Tag, Series, File, Source, Mod, VooblyLadder,
    Player, Civilization, Map, VooblyClan, Team
)
from mgzdb.util import copy_file, parse_filename_timestamp
from mgzdb.compress import compress


LOGGER = logging.getLogger(__name__)
LOG_ID_LENGTH = 8
COMPRESSED_EXT = '.mgc'
MAP_URL = 'https://aoe2map.net/api/rms/file'

def add_file(
        store_host, store_path, rec_path, source, reference, tags,
        series=None, challonge_id=None, voobly_id=None, played=None,
        force=False, user_data=None
    ):
    """Wrapper around AddFile class for parallelization."""
    obj = AddFile(
        add_file.connections, store_host, store_path # pylint: disable=no-member
    )
    try:
        return obj.add_file(
            rec_path, source, reference, tags, series=series, challonge_id=challonge_id,
            voobly_id=voobly_id, played=played, force=force, user_data=user_data
        )
    except KeyboardInterrupt:
        sys.exit()


class AddFile:
    """Add file to MGZ Database."""

    def __init__(self, connections, store_host, store_path):
        """Initialize sessions."""
        self.store_host = store_host
        self.store_path = store_path
        self.store = connections['store']
        self.session = connections['session']
        self.voobly = connections['voobly']
        self.aoe2map = connections['aoe2map']

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
        new_path = os.path.join(self.store_path, compressed_filename)
        copy_file(io.BytesIO(compress(io.BytesIO(data))), self.store, new_path)
        LOGGER.info("[f:%s] copied to %s:%s", log_id, self.store_host, new_path)

        match_hash = summary.get_hash().hexdigest()
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

        new_file = self._get_unique(
            File, ['hash'],
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
        completed = summary.get_completed()
        restored, _ = summary.get_restored()
        has_postgame = bool(postgame)
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
            postgame=has_postgame,
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
            player = self._get_unique(
                Player,
                ['match_id', 'number'],
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
                match_id=match.id,
                human=data['human'],
                name=data['name'],
                number=data['number'],
                color_id=data['color_id'],
                start_x=data['position'][0],
                start_y=data['position'][1],
                winner=data['winner'],
                mvp=data['mvp'],
                score=data['score']
            )
            if match.voobly:
                self._guess_match_user(player, data['name'])

        if tags:
            self._add_tags(match, tags)
        match.winning_team_id = winning_team_id
        return match

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

    def _get_by_keys(self, table, keys, **kwargs):
        """Get object by unique keys."""
        return self.session.query(table).filter_by(**{k:kwargs[k] for k in keys}).one()

    def _get_unique(self, table, keys=None, **kwargs):
        """Get unique object either by query or creation."""
        if not keys:
            keys = ['name']
        if not any([kwargs[k] is not None for k in keys]):
            return None
        try:
            return self._get_by_keys(table, keys, **kwargs)
        except NoResultFound:
            self.session.begin_nested()
            try:
                obj = table(**kwargs)
                self.session.add(obj)
                self.session.commit()
                return obj
            except IntegrityError:
                self.session.rollback()
                return self._get_by_keys(table, keys, **kwargs)
