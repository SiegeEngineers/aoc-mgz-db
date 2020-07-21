"""MGZ database API."""

import io
import logging
import os
import time
from datetime import timedelta, datetime

import pkg_resources
import requests
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import IntegrityError

import mgz.summary

from mgzdb.platforms import PLATFORM_VOOBLY, PLATFORM_IGZ
from mgzdb.schema import (
    Match, SeriesMetadata, File, Player,
    Team, User, Series, Dataset, EventMap, Chat,
    Tournament, Round
)
from mgzdb.util import parse_filename, save_file, get_unique
from mgzdb.compress import compress, compress_tiles, compress_objects
from mgzdb.extract import save_extraction
from mgz.util import Version
from mgz.summary.chat import Chat as ChatType


LOGGER = logging.getLogger(__name__)
LOG_ID_LENGTH = 8
COMPRESSED_EXT = '.mgc'


def has_transposition(user_data, players):
    """Check for player data transposition.

    Occasionally platforms will incorrectly record
    match metadata, so we check it against the rec
    to make sure it's accurate.
    """
    if not user_data:
        return False
    from_rec = {}
    if not all(['color_id' in p for p in user_data]):
        return False
    if not all(['username' in p for p in user_data]):
        return False
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
        return True
    return False


def merge_platform_attributes(ladder, platform_id, match_id, data, platforms):
    """Merge various platform attributes."""
    rated = data['rated']
    if ladder:
        rated = True
    if not ladder:
        ladder = data['ladder']
    if data['platform_id'] and not platform_id:
        platform_id = data['platform_id']
    if data['platform_match_id'] and not match_id:
        match_id = data['platform_match_id']
    ladder_id = None
    if platform_id:
        try:
            ladder_id = platforms[platform_id].lookup_ladder_id(ladder)
        except (KeyError, ValueError, NotImplementedError):
            ladder_id = None
    return rated, ladder_id, platform_id, match_id


def file_exists(session, file_hash, series_name, series_id, modified):
    """Check if a file exists.

    Update the series_id if necessary.
    """
    exists = session.query(File).filter_by(hash=file_hash).one_or_none()
    if exists:
        #exists.modified = modified
        return series_match_exists(session, exists.match, series_id, series_name)
    return False


def series_match_exists(session, match, series_id, series_name):
    if series_id:
        data = session.query(Tournament.event_id, Tournament.id).join(Round).join(Series).filter(Series.id == series_id).one_or_none()
        match.event_id = data[0]
        match.tournament_id = data[1]
        match.series_id = series_id
        get_unique(
            session,
            SeriesMetadata,
            ['series_id'],
            name=series_name,
            series_id=series_id
        )
        session.commit()
    return match.id



def save_chat(session, chats, match_id):
    """Save chat messages."""
    objs = []
    for chat in chats:
        if chat['type'] != ChatType.MESSAGE:
            continue
        del chat['type']
        chat['timestamp'] = timedelta(milliseconds=chat['timestamp'])
        objs.append(Chat(match_id=match_id, **chat))
    session.bulk_save_objects(objs)
    session.commit()


class AddFile:
    """Add file to MGZ Database."""

    def __init__(self, session, platforms, store_path, playback):
        """Initialize sessions."""
        self.session = session
        self.platforms = platforms
        self.store_path = store_path
        self.playback = playback

    def add_file( # pylint: disable=too-many-return-statements, too-many-branches
            self, rec_path, reference, series_name=None,
            series_id=None, platform_id=None, platform_match_id=None,
            platform_metadata=None, played=None, ladder=None, user_data=None
    ):
        """Add a single mgz file."""
        start = time.time()
        if not os.path.isfile(rec_path):
            LOGGER.error("%s is not a file", rec_path)
            return False, 'Not a file'

        original_filename = os.path.basename(rec_path)
        modified = datetime.fromtimestamp(os.path.getmtime(rec_path))

        with open(rec_path, 'rb') as handle:
            data = handle.read()

        try:
            handle = io.BytesIO(data)
            playback = self.playback
            if rec_path.endswith('aoe2record') and os.path.exists(rec_path.replace('.aoe2record', '.json')):
                playback = open(rec_path.replace('.aoe2record', '.json'))
            summary = mgz.summary.Summary(handle, playback)
            # Hash against body only because header can vary based on compression
            file_hash = summary.get_file_hash()
            log_id = file_hash[:LOG_ID_LENGTH]
            LOGGER.info("[f:%s] add started", log_id)
        except RuntimeError as error:
            LOGGER.error("[f] invalid mgz file: %s", str(error))
            return False, 'Invalid mgz file'
        except LookupError:
            LOGGER.error("[f] unknown encoding")
            return False, 'Unknown text encoding'
        except ValueError as error:
            LOGGER.error("[f] error: %s", error)
            return False, error

        existing_match_id = file_exists(self.session, file_hash, series_name, series_id, modified)
        if existing_match_id:
            LOGGER.warning("[f:%s] file already exists (%d)", log_id, existing_match_id)
            #self._handle_file(file_hash, data, Version(summary.get_version()[0]))
            return None, existing_match_id

        try:
            encoding = summary.get_encoding()
        except ValueError as error:
            LOGGER.error("[f] error: %s", error)
            return False, error
        match_hash_obj = summary.get_hash()
        if not match_hash_obj:
            LOGGER.error("f:%s] not enough data to calculate safe match hash", log_id)
            return False, 'Not enough data to calculate safe match hash'
        match_hash = match_hash_obj.hexdigest()
        build = None

        try:
            if not platform_match_id and summary.get_platform()['platform_match_id']:
                platform_match_id = summary.get_platform()['platform_match_id']
            where = (Match.hash == match_hash)
            if platform_match_id:
                where |= (Match.platform_match_id == platform_match_id)
            match = self.session.query(Match).filter(where).one()
            LOGGER.info("[f:%s] match already exists (%d); appending", log_id, match.id)
            series_match_exists(self.session, match, series_id, series_name)
        except MultipleResultsFound:
            LOGGER.error("[f:%s] mismatched hash and match id: %s, %s", log_id, match_hash, platform_match_id)
            return False, 'Mismatched hash and match id'
        except NoResultFound:
            LOGGER.info("[f:%s] adding match", log_id)
            parsed_played, build = parse_filename(original_filename)
            if not played:
                played = parsed_played
            try:
                match, message = self._add_match(
                    summary, played, match_hash, user_data, series_name,
                    series_id, platform_id, platform_match_id,
                    platform_metadata, ladder, build
                )
                if not match:
                    return False, message
                self._update_match_users(platform_id, match.id, user_data)
                self._update_match_de(match)
            except IntegrityError:
                LOGGER.error("[f:%s] constraint violation: could not add match", log_id)
                return False, 'Failed to add match'

        compressed_filename, compressed_size = self._handle_file(file_hash, data, Version(match.version_id))

        try:
            new_file = get_unique(
                self.session,
                File, ['hash'],
                filename=compressed_filename,
                original_filename=original_filename,
                hash=file_hash,
                size=summary.size,
                modified=modified,
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
            return False, 'File hash collision'

        LOGGER.info("[f:%s] add finished in %.2f seconds, file id: %d, match id: %d",
                    log_id, time.time() - start, new_file.id, match.id)
        return file_hash, match.id

    def _add_match( # pylint: disable=too-many-branches, too-many-return-statements
            self, summary, played, match_hash, user_data,
            series_name=None, series_id=None, platform_id=None,
            platform_match_id=None, platform_metadata=None, ladder=None, build=None
    ):
        """Add a match."""
        try:
            duration = summary.get_duration()
        except RuntimeError:
            LOGGER.error("[m] failed to get duration")
            return False, 'Failed to get duration'

        log_id = match_hash[:LOG_ID_LENGTH]
        platform_data = summary.get_platform()
        rated, ladder_id, platform_id, platform_match_id = merge_platform_attributes(ladder, platform_id, platform_match_id, platform_data, self.platforms)

        settings = summary.get_settings()
        try:
            map_data = summary.get_map()
        except ValueError:
            LOGGER.error("[m:%s] has an invalid map", log_id)
            return False, 'Invalid map'
        completed = summary.get_completed()
        restored, _ = summary.get_restored()
        has_postgame = summary.has_achievements()
        version_id, game_version, save_version, log_version = summary.get_version()
        try:
            dataset_data = summary.get_dataset()
        except ValueError:
            LOGGER.error("[m:%s] dataset inconclusive", log_id)
            return False, 'Inconclusive dataset'

        teams = summary.get_teams()
        diplomacy = summary.get_diplomacy()
        players = list(summary.get_players())
        mirror = summary.get_mirror()
        if platform_match_id:
            log_id += ':{}'.format(platform_match_id)

        if restored:
            LOGGER.error("[m:%s] is restored game", log_id)
            return False, 'Restored matches not supported'

        if not completed:
            LOGGER.error("[m:%s] was not completed", log_id)
            return False, 'Incomplete matches not supported'

        if user_data and len(players) != len(user_data):
            LOGGER.error("[m:%s] has mismatched user data", log_id)
            return False, 'Mismatched user data'

        if has_transposition(user_data, players):
            LOGGER.error("[m:%s] has mismatched user data (transposition)", log_id)
            return False, 'Transposed user data'

        try:
            dataset = self.session.query(Dataset).filter_by(id=dataset_data['id']).one()
        except NoResultFound:
            LOGGER.error("[m:%s] dataset not supported: userpatch id: %s (%s)",
                         log_id, dataset_data['id'], dataset_data['name'])
            return False, 'Dataset not supported'

        series, tournament, event, event_map_id = self._handle_series(series_id, series_name, map_data, log_id)
        if series and series.played:
            played = series.played

        objects = summary.get_objects()

        match = get_unique(
            self.session,
            Match, ['hash', 'platform_match_id'],
            platform_match_id=platform_match_id,
            platform_id=platform_id,
            platform_metadata=platform_metadata,
            played=played,
            hash=match_hash,
            series=series,
            tournament=tournament,
            event=event,
            version_id=version_id.value,
            game_version=game_version,
            save_version=round(save_version, 2),
            log_version=log_version,
            build=build,
            dataset=dataset,
            dataset_version=dataset_data['version'],
            ladder_id=ladder_id,
            rated=rated,
            lobby_name=platform_data['lobby_name'],
            objects=compress_objects(objects['objects']),
            builtin_map_id=map_data['id'],
            event_map_id=event_map_id,
            map_size_id=map_data['dimension'],
            map_name=map_data['name'],
            map_tiles=compress_tiles(map_data['tiles']),
            rms_seed=map_data['seed'],
            rms_zr=map_data['zr'],
            rms_custom=map_data['custom'],
            guard_state=map_data['modes']['guard_state'],
            direct_placement=map_data['modes']['direct_placement'],
            effect_quantity=map_data['modes']['effect_quantity'],
            fixed_positions=map_data['modes']['fixed_positions'],
            water_percent=map_data['water'],
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
            treaty_length=settings['treaty_length'],
            starting_resources_id=settings['starting_resources'][0],
            starting_age_id=settings['starting_age'][0],
            victory_condition_id=settings['victory_condition'][0],
            team_together=settings['team_together'],
            all_technologies=settings['all_technologies'],
            lock_speed=settings['lock_speed'],
            multiqueue=settings['multiqueue'],
            diplomacy_type=diplomacy['type'],
            team_size=diplomacy.get('team_size'),
            mirror=mirror,
            starting_town_centers=objects.get('tcs'),
            starting_walls=objects.get('stone_walls'),
            starting_palisades=objects.get('palisade_walls')
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
            try:
                get_unique(
                    self.session,
                    Team,
                    ['match', 'team_id'],
                    winner=(team_id == winning_team_id),
                    match=match,
                    team_id=team_id
                )
                if data['user_id']:
                    get_unique(self.session, User, ['id', 'platform_id'], id=str(data['user_id']), platform_id=platform_id)
                player = get_unique(
                    self.session,
                    Player,
                    ['match_id', 'number'],
                    civilization_id=int(data['civilization']),
                    team_id=team_id,
                    match_id=match.id,
                    dataset=dataset,
                    platform_id=platform_id,
                    user_id=data['user_id'],
                    user_name=data['name'] if data['user_id'] else None,
                    human=data['human'],
                    name=data['name'],
                    number=data['number'],
                    color_id=data['color_id'],
                    start_x=data['position'][0],
                    start_y=data['position'][1],
                    winner=data['winner'],
                    mvp=data['mvp'],
                    cheater=data['cheater'],
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
            except RuntimeError:
                LOGGER.warning("[m:%s] failed to insert players (probably bad civ id: %d)", log_id, data['civilization'])
                return False, 'Failed to load players'

            if match.platform_id in [PLATFORM_VOOBLY, PLATFORM_IGZ] and not user_data and player.human:
                self._guess_match_user(player, data['name'], match.platform_id)


        match.winning_team_id = winning_team_id
        success, attrs = save_extraction(self.session, summary, ladder_id, match.id, dataset_data['id'], log_id)
        if success:
            match.has_playback = True
            match.state_reader_version = attrs['version']
            match.state_reader_interval = attrs['interval']
            match.state_reader_runtime = attrs['runtime']

        save_chat(self.session, summary.get_chat(), match.id)
        return match, None

    def _update_match_de(self, match):
        if match.platform_id != 'de':
            return
        resp = requests.get('https://aoe2.net/api/match?uuid={}'.format(match.platform_match_id))
        if resp.status_code != 200:
            LOGGER.warning('failed to get aoe2.net data')
            return
        data = resp.json()
        if data['started']:
            match.played = datetime.fromtimestamp(data['started'])
        match.rated = data['ranked']
        match.lobby_private = data['has_password']
        match.lobby_opened = datetime.fromtimestamp(data['opened'])
        match.server = data['server']
        match.ladder_id = data['leaderboard_id']
        if data['version']:
            match.build = '101.101.{}.0'.format(data['version'])
            match.dataset_version = match.build
        for pdata in data['players']:
            if not pdata['profile_id']:
                continue
            try:
                player = self.session.query(Player).filter_by(match_id=match.id, user_id=str(pdata['profile_id'])).one()
            except NoResultFound:
                LOGGER.error("failed to find p%d to update platform user data", p['color'])
                continue
            LOGGER.info("[m:%s] updating platform user data for p%d", match.hash[:LOG_ID_LENGTH], pdata['color'])
            get_unique(self.session, User, ['id', 'platform_id'], id=str(pdata['profile_id']), platform_id=match.platform_id)
            player.rate_snapshot = pdata['rating']


    def _update_match_users(self, platform_id, match_id, user_data):
        """Update Voobly User info on Match."""
        if not user_data:
            return
        if not all(['color_id' in p for p in user_data]):
            return
        if not all(['username' in p for p in user_data]):
            return
        for user in user_data:
            try:
                player = self.session.query(Player).filter_by(match_id=match_id, color_id=user['color_id']).one()
            except NoResultFound:
                LOGGER.error("failed to find p%d to update platform user data",
                             user['color_id'] + 1)
                continue
            if not player.human:
                continue
            LOGGER.info("[m:%s] updating platform user data for p%d",
                        player.match.hash[:LOG_ID_LENGTH], user['color_id'] + 1)
            get_unique(self.session, User, ['id', 'platform_id'], id=str(user['id']), platform_id=platform_id)
            player.user_id = str(user['id'])
            player.user_name = user.get('username')
            player.platform_id = platform_id
            player.rate_before = user.get('rate_before')
            player.rate_after = user.get('rate_after')
            if not player.rate_snapshot:
                player.rate_snapshot = user.get('rate_snapshot')

    def _guess_match_user(self, player, name, platform_id):
        """Guess Voobly User from a player name."""
        try:
            user_id = str(self.platforms[platform_id].find_user(name.lstrip('+')))
            get_unique(
                self.session,
                User, ['id', 'platform_id'],
                id=user_id,
                platform_id=platform_id
            )
            player.user_id = user_id
            player.user_name = name.lstrip('+')
        except RuntimeError as error:
            LOGGER.warning("failed to lookup %s user: %s", platform_id, error)

    def _handle_series(self, series_id, series_name, map_data, log_id):
        """Handle series-related tasks."""
        if series_id and series_name:
            series = self.session.query(Series).get(series_id)
            if series:
                get_unique(
                    self.session,
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

    def _handle_file(self, file_hash, data, version):
        """Handle file: compress and store."""
        compressed_filename = '{}{}'.format(file_hash, COMPRESSED_EXT)
        compressed_data = compress(io.BytesIO(data), version=version)
        destination = save_file(compressed_data, self.store_path, compressed_filename)
        LOGGER.info("[f:%s] copied to %s", file_hash[:LOG_ID_LENGTH], destination)
        return compressed_filename, len(compressed_data)
