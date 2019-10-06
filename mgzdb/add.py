"""MGZ database API."""

import hashlib
import io
import logging
import os
import sys
import time
from datetime import timedelta

import pkg_resources
import requests
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import IntegrityError

import voobly
import mgz.const
import mgz.summary

from aocref.model import Series, Dataset, EventMap
from mgzdb.platforms import PLATFORM_VOOBLY, VOOBLY_PLATFORMS
from mgzdb.schema import (
    Match, SeriesMetadata, File, Ladder, Player,
    Team, User
)
from mgzdb.util import parse_filename_timestamp, save_file
from mgzdb.compress import compress


LOGGER = logging.getLogger(__name__)
LOG_ID_LENGTH = 8
COMPRESSED_EXT = '.mgc'


def add_file(
        store_path, rec_path, reference,
        series=None, series_id=None, platform_id=None,
        platform_match_id=None, played=None, ladder=None,
        user_data=None
    ):
    """Wrapper around AddFile class for parallelization."""
    obj = AddFile(
        add_file.connections, store_path # pylint: disable=no-member
    )
    try:
        return obj.add_file(
            rec_path, reference, series_name=series,
            series_id=series_id, platform_id=platform_id,
            platform_match_id=platform_match_id, played=played,
            ladder=ladder, user_data=user_data
        )
    except KeyboardInterrupt:
        sys.exit()


class AddFile:
    """Add file to MGZ Database."""

    def __init__(self, connections, store_path):
        """Initialize sessions."""
        self.store_path = store_path
        self.session = connections['session']
        self.platforms = connections['platforms']
        self.aoe2map = connections['aoe2map']

    def add_file( # pylint: disable=too-many-return-statements, too-many-branches
            self, rec_path, reference, series_name=None,
            series_id=None, platform_id=None, platform_match_id=None,
            played=None, ladder=None, user_data=None
    ):
        """Add a single mgz file."""
        start = time.time()
        if not os.path.isfile(rec_path):
            LOGGER.error("%s is not a file", rec_path)
            return False

        original_filename = os.path.basename(rec_path)

        with open(rec_path, 'rb') as handle:
            data = handle.read()

        try:
            handle = io.BytesIO(data)
            summary = mgz.summary.Summary(handle, len(data))
            # Hash against body only because header can vary based on compression
            file_hash = hashlib.sha1(data[summary.body_position:]).hexdigest()
            log_id = file_hash[:LOG_ID_LENGTH]
            LOGGER.info("[f:%s] add started", log_id)
        except RuntimeError:
            LOGGER.error("[f] invalid mgz file")
            return False

        if self.session.query(File).filter_by(hash=file_hash).count() > 0:
            LOGGER.warning("[f:%s] file already exists", log_id)
            return False

        try:
            summary.work()
        except RuntimeError:
            LOGGER.error("[f:%s] failed to parse mgz", log_id)
            return False

        encoding = summary.get_encoding()
        if encoding == 'unknown':
            LOGGER.warning("[f:%s] unknown file text encoding", log_id)
            return False

        match_hash_obj = summary.get_hash()
        if not match_hash_obj:
            LOGGER.error("f:%s] not enough data to calculate safe match hash", log_id)
            return False
        match_hash = match_hash_obj.hexdigest()

        try:
            where = (Match.hash == match_hash)
            if platform_match_id:
                where |= (Match.platform_match_id == platform_match_id)
            match = self.session.query(Match).filter(where).one()
            LOGGER.info("[f:%s] match already exists (%d); appending", log_id, match.id)
        except MultipleResultsFound:
            LOGGER.error("[f:%s] mismatched hash and match id: %s, %s", log_id, match_hash, platform_match_id)
            return False
        except NoResultFound:
            LOGGER.info("[f:%s] adding match", log_id)
            if not played:
                played = parse_filename_timestamp(original_filename)
            try:
                match = self._add_match(
                    summary, played, match_hash, user_data, series_name,
                    series_id, platform_id, platform_match_id, ladder
                )
                if not match:
                    return False
                self._update_match_users(platform_id, match.id, user_data)
            except IntegrityError:
                LOGGER.error("[f:%s] constraint violation: could not add match", log_id)
                return False

        compressed_filename, compressed_size = self._handle_file(file_hash, data)

        try:
            new_file = self._get_unique(
                File, ['hash'],
                filename=compressed_filename,
                original_filename=original_filename,
                hash=file_hash,
                size=summary.size,
                compressed_size=compressed_size,
                encoding=encoding,
                language=summary.get_language(),
                reference=reference,
                match=match,
                owner_number=summary.get_owner(),
                parser_version=pkg_resources.get_distribution('mgz').version
            )
            self.session.add(new_file)
            self.session.commit()
        except RuntimeError:
            LOGGER.error("[f:%s] unable to add file, likely hash collision", log_id)
            return False

        LOGGER.info("[f:%s] add finished in %.2f seconds, file id: %d, match id: %d",
                    log_id, time.time() - start, new_file.id, match.id)
        return True

    def _add_match( # pylint: disable=too-many-branches, too-many-return-statements
            self, summary, played, match_hash, user_data,
            series_name=None, series_id=None, platform_id=None,
            platform_match_id=None, ladder=None
    ):
        """Add a match."""
        try:
            postgame = summary.get_postgame()
            duration = summary.get_duration()
        except RuntimeError:
            LOGGER.error("[m] failed to get duration")
            return False

        log_id = match_hash[:LOG_ID_LENGTH]
        rated = False
        from_voobly, ladder_name, rated, _ = summary.get_ladder()
        if ladder:
            rated = True
        if not ladder:
            ladder = ladder_name
        if from_voobly and not platform_id:
            platform_id = PLATFORM_VOOBLY
        settings = summary.get_settings()
        try:
            map_data = summary.get_map()
        except ValueError:
            LOGGER.error("[m:%s] has an invalid map", log_id)
            return False
        completed = summary.get_completed()
        restored, _ = summary.get_restored()
        has_postgame = bool(postgame)
        major_version, minor_version = summary.get_version()
        try:
            dataset_data = summary.get_dataset()
        except ValueError:
            LOGGER.error("[m:%s] dataset inconclusive", log_id)
            return False
        teams = summary.get_teams()
        diplomacy = summary.get_diplomacy()
        players = list(summary.get_players())
        mirror = summary.get_mirror()
        if platform_match_id:
            log_id += ':{}'.format(platform_match_id)

        if restored:
            LOGGER.error("[m:%s] is restored game", log_id)
            return False

        if not completed:
            LOGGER.error("[m:%s] was not completed", log_id)
            return False

        if user_data and len(players) != len(user_data):
            LOGGER.error("[m:%s] has mismatched user data", log_id)
            return False

        if user_data:
            from_rec = {}
            for player in players:
                from_rec[player['color_id']] = player['name']
            from_user_data = {}
            for user in user_data:
                from_user_data[user['color_id']] = user['username']
            strike = 0
            for color_id, name in from_rec.items():
                if (
                        color_id not in from_user_data or
                        from_user_data[color_id].lower() not in name.lower() and
                        name.lower() not in from_user_data[color_id].lower()
                    ):
                    strike += 1
            if strike >= len(players) / 2:
                LOGGER.error("[m:%s] has mismatched user data (transposition)", log_id)
                return False

        if platform_id:
            try:
                if platform_id in VOOBLY_PLATFORMS:
                    ladder_id = voobly.lookup_ladder_id(ladder)
                else:
                    ladder_id = 1 # fix..
                ladder = self._get_unique(
                    Ladder, keys=['id', 'platform_id'], id=ladder_id,
                    platform_id=platform_id, name=ladder
                )
            except ValueError:
                ladder_id = None
        else:
            ladder_id = None

        try:
            dataset = self.session.query(Dataset).filter_by(id=dataset_data['id']).one()
        except NoResultFound:
            LOGGER.error("[m:%s] dataset not supported: userpatch id: %s (%s)",
                         log_id, dataset_data['id'], dataset_data['name'])
            return False

        series, tournament, event, event_map_id = self._handle_series(series_id, series_name, map_data, log_id)
        if series:
            played = series.played

        match = self._get_unique(
            Match, ['hash', 'platform_match_id'],
            platform_match_id=platform_match_id,
            platform_id=platform_id,
            played=played,
            hash=match_hash,
            series=series,
            tournament=tournament,
            event=event,
            version=major_version,
            minor_version=minor_version,
            dataset=dataset,
            dataset_version=dataset_data['version'],
            ladder_id=ladder_id,
            rated=rated,
            builtin_map_id=map_data['id'],
            event_map_id=event_map_id,
            map_size_id=map_data['dimension'],
            map_name=map_data['name'],
            rms_seed=map_data['seed'],
            rms_zr=map_data['zr'],
            rms_custom=map_data['custom'],
            guard_state=map_data['modes']['guard_state'],
            direct_placement=map_data['modes']['direct_placement'],
            effect_quantity=map_data['modes']['effect_quantity'],
            fixed_positions=map_data['modes']['fixed_positions'],
            duration=timedelta(milliseconds=duration),
            completed=completed,
            restored=restored,
            postgame=has_postgame,
            type_id=settings['type'][0],
            difficulty_id=settings['difficulty'][0],
            population_limit=settings['population_limit'],
            map_reveal_choice_id=settings['map_reveal_choice'][0],
            speed_id=settings['speed'][0],
            cheats=settings['cheats'],
            lock_teams=settings['lock_teams'],
            starting_resources_id=settings['starting_resources'][0],
            starting_age_id=settings['starting_age'][0],
            victory_condition_id=settings['victory_condition'][0],
            team_together=settings['team_together'],
            all_technologies=settings['all_technologies'],
            lock_speed=settings['lock_speed'],
            multiqueue=settings['multiqueue'],
            diplomacy_type=diplomacy['type'],
            team_size=diplomacy.get('team_size'),
            mirror=mirror
        )

        winning_team_id = None
        for data in players:
            team_id = None
            for i, team in enumerate(teams):
                if data['number'] in team:
                    team_id = i
            if data['winner']:
                winning_team_id = team_id
            feudal_time = data['achievements']['technology']['feudal_time']
            castle_time = data['achievements']['technology']['castle_time']
            imperial_time = data['achievements']['technology']['imperial_time']
            self._get_unique(
                Team,
                ['match', 'team_id'],
                winner=(team_id == winning_team_id),
                match=match,
                team_id=team_id
            )
            player = self._get_unique(
                Player,
                ['match_id', 'number'],
                civilization_id=int(data['civilization']),
                team_id=team_id,
                match_id=match.id,
                dataset=dataset,
                platform_id=platform_id,
                human=data['human'],
                name=data['name'],
                number=data['number'],
                color_id=data['color_id'],
                start_x=data['position'][0],
                start_y=data['position'][1],
                winner=data['winner'],
                mvp=data['mvp'],
                score=data['score'],
                rate_snapshot=data['rate_snapshot'],
                military_score=data['achievements']['military']['score'],
                units_killed=data['achievements']['military']['units_killed'],
                hit_points_killed=data['achievements']['military']['hit_points_killed'],
                units_lost=data['achievements']['military']['units_lost'],
                buildings_razed=data['achievements']['military']['buildings_razed'],
                hit_points_razed=data['achievements']['military']['hit_points_razed'],
                buildings_lost=data['achievements']['military']['buildings_lost'],
                units_converted=data['achievements']['military']['units_converted'],
                economy_score=data['achievements']['economy']['score'],
                food_collected=data['achievements']['economy']['food_collected'],
                wood_collected=data['achievements']['economy']['wood_collected'],
                stone_collected=data['achievements']['economy']['stone_collected'],
                gold_collected=data['achievements']['economy']['gold_collected'],
                tribute_sent=data['achievements']['economy']['tribute_sent'],
                tribute_received=data['achievements']['economy']['tribute_received'],
                trade_gold=data['achievements']['economy']['trade_gold'],
                relic_gold=data['achievements']['economy']['relic_gold'],
                technology_score=data['achievements']['technology']['score'],
                feudal_time=timedelta(seconds=feudal_time) if feudal_time else None,
                castle_time=timedelta(seconds=castle_time) if castle_time else None,
                imperial_time=timedelta(seconds=imperial_time) if imperial_time else None,
                explored_percent=data['achievements']['technology']['explored_percent'],
                research_count=data['achievements']['technology']['research_count'],
                research_percent=data['achievements']['technology']['research_percent'],
                society_score=data['achievements']['society']['score'],
                total_wonders=data['achievements']['society']['total_wonders'],
                total_castles=data['achievements']['society']['total_castles'],
                total_relics=data['achievements']['society']['total_relics'],
                villager_high=data['achievements']['society']['villager_high']
            )
            if match.platform_id == PLATFORM_VOOBLY and not user_data:
                self._guess_match_user(player, data['name'])

        match.winning_team_id = winning_team_id
        return match

    def _update_match_users(self, platform_id, match_id, user_data):
        """Update Voobly User info on Match."""
        if user_data:
            for user in user_data:
                try:
                    player = self.session.query(Player).filter_by(match_id=match_id, color_id=user['color_id']).one()
                except NoResultFound:
                    LOGGER.error("failed to find p%d to update platform user data",
                                 user['color_id'] + 1)
                    continue
                LOGGER.info("[m:%s] updating platform user data for p%d",
                            player.match.hash[:LOG_ID_LENGTH], user['color_id'] + 1)
                self._get_unique(User, ['id', 'platform_id'], id=str(user['id']), platform_id=platform_id)
                player.user_id = str(user['id'])
                player.user_name = user.get('username')
                player.platform_id = platform_id
                player.rate_before = user.get('rate_before')
                player.rate_after = user.get('rate_after')
                if not player.rate_snapshot:
                    player.rate_snapshot = user.get('rate_snapshot')

    def _guess_match_user(self, player, name):
        """Guess Voobly User from a player name."""
        try:
            user_id = str(self.platforms[PLATFORM_VOOBLY].find_user(name.lstrip('+')))
            self._get_unique(
                User, ['id', 'platform_id'],
                id=user_id,
                platform_id=PLATFORM_VOOBLY
            )
            player.user_id = user_id
        except (voobly.VooblyError, requests.exceptions.ConnectionError) as error:
            LOGGER.warning("failed to lookup Voobly user: %s", error)

    def _handle_series(self, series_id, series_name, map_data, log_id):
        """Handle series-related tasks."""
        if series_id and series_name:
            series = self.session.query(Series).get(series_id)
            if series:
                self._get_unique(
                    SeriesMetadata,
                    ['series_id'],
                    name=series_name,
                    series_id=series.id
                )
                tournament = series.tournament
                event = tournament.event
                event_map = self.session.query(EventMap) \
                    .filter(EventMap.event_id == event.id) \
                    .filter(EventMap.name == map_data['name']) \
                    .one_or_none()
                if event_map:
                    event_map_id = event_map.id
                else:
                    event_map_id = None
                    LOGGER.warning("[m:%s] event map for %s not found: %s", log_id, event.id, map_data['name'])
                return series, tournament, event, event_map_id
        try:
            event_map = self.session.query(EventMap) \
                .filter(EventMap.name == map_data['name']) \
                .one()
            event_map_id = event_map.id
            LOGGER.info("[m:%s] guessed event %s for map %s", log_id, event_map.event_id, map_data['name'])
        except (NoResultFound, MultipleResultsFound):
            event_map_id = None
        return None, None, None, event_map_id

    def _handle_file(self, file_hash, data):
        """Handle file: compress and store."""
        compressed_filename = '{}{}'.format(file_hash, COMPRESSED_EXT)
        compressed_data = compress(io.BytesIO(data))
        destination = save_file(compressed_data, self.store_path, compressed_filename)
        LOGGER.info("[f:%s] copied to %s", file_hash[:LOG_ID_LENGTH], destination)
        return compressed_filename, len(compressed_data)

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
                try:
                    return self._get_by_keys(table, keys, **kwargs)
                except NoResultFound:
                    raise RuntimeError
