"""MGZ database schema."""

from sqlalchemy import (
    create_engine, Boolean, DateTime, Column,
    ForeignKey, Integer, Interval, String, Float, LargeBinary
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, backref
from sqlalchemy.schema import ForeignKeyConstraint, UniqueConstraint

from mgzdb.util import get_utc_now


BASE = declarative_base()


def get_session(url):
    """Get SQL session."""
    engine = create_engine(url, echo=False)
    session = sessionmaker(bind=engine)()
    return session, engine


class Platform(BASE):
    """Multiplayer platform."""
    __tablename__ = 'platforms'
    id = Column(String, primary_key=True)
    name = Column(String)
    url = Column(String)
    match_url = Column(String)


class Person(BASE):
    """A known player."""
    __tablename__ = 'people'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    country = Column(String)
    aoeelo_id = Column(Integer)
    aoeelo_rate = Column(Integer)
    aoeelo_rank = Column(Integer)
    esportsearnings_id = Column(Integer)
    liquipedia = Column(String)
    earnings = Column(Float)
    first_name = Column(String)
    last_name = Column(String)
    birthday = Column(DateTime)
    portrait = Column(LargeBinary)
    twitch = Column(String)
    mixer = Column(String)
    youtube = Column(String)
    discord = Column(String)
    douyu = Column(String)


class Event(BASE):
    """Event (one or more tournaments)."""
    __tablename__ = 'events'
    id = Column(String, primary_key=True)
    name = Column(String)
    year = Column(Integer)


class Tournament(BASE):
    """A specific tournament (or stage of an event)."""
    __tablename__ = 'tournaments'
    id = Column(String, primary_key=True)
    name = Column(String)
    event_id = Column(String, ForeignKey('events.id'), index=True)
    event = relationship('Event', foreign_keys=[event_id], backref='tournaments')


class Round(BASE):
    """Tournament round."""
    __tablename__ = 'rounds'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    tournament_id = Column(String, ForeignKey('tournaments.id'), index=True)
    tournament = relationship('Tournament', foreign_keys=[tournament_id], backref='rounds')


class Series(BASE):
    """Series of matches."""
    __tablename__ = 'series'
    id = Column(String, primary_key=True)
    round_id = Column(Integer, ForeignKey('rounds.id'), index=True)
    round = relationship('Round', foreign_keys=[round_id], backref='series')
    played = Column(DateTime)
    tournament = relationship(
        'Tournament',
        secondary='rounds',
        primaryjoin='Series.round_id == Round.id',
        secondaryjoin='Tournament.id == Round.tournament_id',
        viewonly=True,
        uselist=False
    )


class Participant(BASE):
    """Series participants (team or single player)."""
    __tablename__ = 'participants'
    id = Column(Integer, primary_key=True)
    series_id = Column(String, ForeignKey('series.id'), index=True)
    series = relationship('Series', foreign_keys=[series_id], backref='participants')
    name = Column(String)
    score = Column(Integer)
    winner = Column(Boolean)


class Dataset(BASE):
    """AoC Dataset (a specific set of civs/balance/etc)."""
    __tablename__ = 'datasets'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    short = Column(String)


class Civilization(BASE):
    """Civilization belonging to a dataset."""
    __tablename__ = 'civilizations'
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), primary_key=True)
    dataset = relationship('Dataset', foreign_keys=[dataset_id])
    name = Column(String, nullable=False)


class CivilizationBonus(BASE):
    """Bonus belonging to civilization."""
    __tablename__ = 'civilization_bonuses'
    id = Column(Integer, primary_key=True)
    civilization_id = Column(Integer)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), index=True)
    type = Column(String)
    description = Column(String)
    civilization = relationship(
        'Civilization',
        foreign_keys=[civilization_id, dataset_id],
        backref='bonuses'
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ['civilization_id', 'dataset_id'], ['civilizations.id', 'civilizations.dataset_id']
        ),
    )


class EventMap(BASE):
    """Event map."""
    __tablename__ = 'event_maps'
    id = Column(Integer, primary_key=True)
    event_id = Column(String, ForeignKey('events.id'), index=True)
    event = relationship('Event', foreign_keys=event_id, backref='maps')
    name = Column(String, index=True)
    zr = Column(Boolean)
    aoe2mapnet_id = Column(String)


class Map(BASE):
    """Builtin map."""
    __tablename__ = 'maps'
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), primary_key=True)
    dataset = relationship('Dataset', foreign_keys=[dataset_id])
    name = Column(String, index=True)


class Technology(BASE):
    """Technology."""
    __tablename__ = 'technologies'
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), primary_key=True)
    dataset = relationship('Dataset', foreign_keys=[dataset_id])
    name = Column(String)


class Object(BASE):
    """Object."""
    __tablename__ = 'objects'
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), primary_key=True)
    dataset = relationship('Dataset', foreign_keys=[dataset_id])
    name = Column(String)


class Terrain(BASE):
    """Terrain."""
    __tablename__ = 'terrain'
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), primary_key=True)
    name = Column(String)
    color_level = Column(String(7))
    color_up = Column(String(7))
    color_down = Column(String(7))


class GameType(BASE):
    """Game type."""
    __tablename__ = 'game_types'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class StartingResources(BASE):
    """Starting resoruces."""
    __tablename__ = 'starting_resources'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class VictoryCondition(BASE):
    """Victory conditions."""
    __tablename__ = 'victory_conditions'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class MapRevealChoice(BASE):
    """Map reveal choices."""
    __tablename__ = 'map_reveal_choices'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class StartingAge(BASE):
    """Starting Ages."""
    __tablename__ = 'starting_ages'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class Difficulty(BASE):
    """Difficulties."""
    __tablename__ = 'difficulties'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class Speed(BASE):
    """Speeds."""
    __tablename__ = 'speeds'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class MapSize(BASE):
    """Map sizes."""
    __tablename__ = 'map_sizes'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class PlayerColor(BASE):
    """Player color."""
    __tablename__ = 'player_colors'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    hex = Column(String)


class File(BASE):
    """Represent File."""
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    match = relationship('Match', foreign_keys=[match_id])
    hash = Column(String, unique=True, nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String)
    modified = Column(DateTime)
    encoding = Column(String)
    language = Column(String, index=True)
    size = Column(Integer, nullable=False)
    compressed_size = Column(Integer, nullable=False)
    owner_number = Column(Integer, nullable=False)
    owner = relationship('Player', foreign_keys=[match_id, owner_number], viewonly=True, post_update=True)
    reference = Column(String)
    added = Column(DateTime, default=get_utc_now)
    parser_version = Column(String, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['match_id', 'owner_number'], ['players.match_id', 'players.number'], ondelete='cascade'),
    )


class Match(BASE):
    """Represents Match."""
    __tablename__ = 'matches'
    id = Column(Integer, primary_key=True)
    hash = Column(String, unique=True)
    series_id = Column(String, ForeignKey('series.id'), index=True)
    tournament_id = Column(String, ForeignKey('tournaments.id'), index=True)
    event_id = Column(String, ForeignKey('events.id'), index=True)
    series = relationship('Series', foreign_keys=series_id, backref='matches')
    tournament = relationship('Tournament', foreign_keys=tournament_id, backref='matches')
    event = relationship('Event', foreign_keys=event_id, backref='matches')
    players = relationship('Player', back_populates='match', cascade='all, delete')
    teams = relationship('Team', foreign_keys='Team.match_id', cascade='all, delete')
    winning_team_id = Column(Integer)
    winning_team = relationship('Player', primaryjoin='and_(Player.match_id==Match.id, ' \
                                                      'Player.team_id==Match.winning_team_id)')
    losers = relationship('Player', primaryjoin='and_(Player.match_id==Match.id, ' \
                                                'Player.team_id!=Match.winning_team_id)')
    files = relationship('File', foreign_keys='File.match_id', cascade='all, delete, delete-orphan', post_update=True)
    version = Column(String)
    minor_version = Column(String)
    version_id = Column(Integer, ForeignKey('versions.id'))
    game_version = Column(String)
    save_version = Column(Float)
    log_version = Column(Integer)
    build = Column(String)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), index=True)
    dataset_version = Column(String)
    dataset = relationship('Dataset', foreign_keys=dataset_id)
    platform_id = Column(String, ForeignKey('platforms.id'), index=True)
    platform = relationship('Platform', foreign_keys=platform_id)
    platform_metadata = Column(String)
    ladder_id = Column(Integer)
    ladder = relationship('Ladder', foreign_keys=[ladder_id, platform_id], viewonly=True)
    rated = Column(Boolean)
    lobby_name = Column(String)
    lobby_private = Column(Boolean)
    lobby_opened = Column(DateTime)
    server = Column(String)
    builtin_map_id = Column(Integer)
    builtin_map = relationship('Map', foreign_keys=[builtin_map_id, dataset_id], backref='matches', viewonly=True)
    map_size_id = Column(Integer, ForeignKey('map_sizes.id'), index=True)
    map_size = relationship('MapSize', foreign_keys=map_size_id)
    map_name = Column(String, index=True)
    map_tiles = Column(LargeBinary)
    objects = Column(LargeBinary)
    event_map_id = Column(Integer, ForeignKey('event_maps.id'), index=True)
    event_map = relationship('EventMap', foreign_keys=event_map_id, backref='matches')
    rms_zr = Column(Boolean)
    rms_custom = Column(Boolean)
    rms_seed = Column(Integer)
    guard_state = Column(Boolean)
    fixed_positions = Column(Boolean)
    direct_placement = Column(Boolean)
    effect_quantity = Column(Boolean)
    water_percent = Column(Float)
    played = Column(DateTime, index=True)
    added = Column(DateTime, default=get_utc_now)
    platform_match_id = Column(String, unique=True)
    duration = Column(Interval)
    completed = Column(Boolean)
    restored = Column(Boolean)
    postgame = Column(Boolean)
    type_id = Column(Integer, ForeignKey('game_types.id'), index=True)
    type = relationship('GameType', foreign_keys=type_id)
    difficulty_id = Column(Integer, ForeignKey('difficulties.id'), index=True)
    difficulty = relationship('Difficulty', foreign_keys=difficulty_id)
    population_limit = Column(Integer)
    map_reveal_choice_id = Column(Integer, ForeignKey('map_reveal_choices.id'), index=True)
    map_reveal_choice = relationship('MapRevealChoice', foreign_keys=map_reveal_choice_id)
    cheats = Column(Boolean)
    speed_id = Column(Integer, ForeignKey('speeds.id'), index=True)
    speed = relationship('Speed', foreign_keys=speed_id)
    lock_teams = Column(Boolean)
    mirror = Column(Boolean)
    diplomacy_type = Column(String, nullable=False, index=True)
    team_size = Column(String, nullable=False, index=True)
    starting_resources_id = Column(Integer, ForeignKey('starting_resources.id'), index=True)
    starting_resources = relationship('StartingResources', foreign_keys=starting_resources_id)
    starting_age_id = Column(Integer, ForeignKey('starting_ages.id'), index=True)
    starting_age = relationship('StartingAge', foreign_keys=starting_age_id)
    starting_town_centers = Column(Integer)
    starting_palisades = Column(Boolean)
    starting_walls = Column(Boolean)
    victory_condition_id = Column(Integer, ForeignKey('victory_conditions.id'), index=True)
    victory_condition = relationship('VictoryCondition', foreign_keys=victory_condition_id)
    treaty_length = Column(Integer)
    team_together = Column(Boolean)
    all_technologies = Column(Boolean)
    lock_speed = Column(Boolean)
    multiqueue = Column(Boolean)
    has_playback = Column(Boolean)
    object_instances = relationship('ObjectInstance', foreign_keys='ObjectInstance.match_id', cascade='all, delete, delete-orphan')
    research = relationship('Research', foreign_keys='Research.match_id', cascade='all, delete, delete-orphan')
    timeseries = relationship('Timeseries', foreign_keys='Timeseries.match_id', cascade='all, delete, delete-orphan')
    market = relationship('Market', foreign_keys='Market.match_id', cascade='all, delete, delete-orphan')
    state_reader_version = Column(String)
    state_reader_interval = Column(Integer)
    state_reader_runtime = Column(Interval)
    hc = Column(Boolean)
    __table_args__ = (
        ForeignKeyConstraint(['ladder_id', 'platform_id'], ['ladders.id', 'ladders.platform_id']),
        ForeignKeyConstraint(['builtin_map_id', 'dataset_id'], ['maps.id', 'maps.dataset_id'])
    )


class Team(BASE):
    """Represent a team."""
    __tablename__ = 'teams'
    team_id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), primary_key=True)
    winner = Column(Boolean)
    match = relationship('Match', foreign_keys=match_id)


class Player(BASE):
    """Represent Player in a Match."""
    __tablename__ = 'players'
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), primary_key=True, index=True)
    name = Column(String, nullable=False)
    number = Column(Integer, nullable=False, primary_key=True, index=True)
    color_id = Column(Integer, ForeignKey('player_colors.id'), nullable=False, index=True)
    color = relationship('PlayerColor', foreign_keys=color_id)
    platform_id = Column(String, ForeignKey('platforms.id'), index=True)
    platform = relationship('Platform', foreign_keys=platform_id)
    user_id = Column(String, index=True)
    user_name = Column(String, index=True)
    user = relationship('User', foreign_keys=[user_id, platform_id], viewonly=True)
    match = relationship('Match', foreign_keys=[match_id], viewonly=True)
    team_id = Column(Integer)
    team = relationship('Team', foreign_keys=[match_id, team_id], backref='members', viewonly=True, single_parent=True, post_update=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    dataset = relationship('Dataset', foreign_keys=[dataset_id])
    civilization_id = Column(Integer, index=True)
    civilization = relationship('Civilization', foreign_keys=[dataset_id, civilization_id], backref='players', viewonly=True)
    start_x = Column(Integer)
    start_y = Column(Integer)
    human = Column(Boolean)
    winner = Column(Boolean)
    mvp = Column(Boolean)
    cheater = Column(Boolean)
    score = Column(Integer)
    rate_before = Column(Float)
    rate_after = Column(Float, index=True)
    rate_snapshot = Column(Float, index=True)
    military_score = Column(Integer)
    units_killed = Column(Integer)
    hit_points_killed = Column(Integer)
    units_lost = Column(Integer)
    buildings_razed = Column(Integer)
    hit_points_razed = Column(Integer)
    buildings_lost = Column(Integer)
    units_converted = Column(Integer)
    economy_score = Column(Integer)
    food_collected = Column(Integer)
    wood_collected = Column(Integer)
    stone_collected = Column(Integer)
    gold_collected = Column(Integer)
    tribute_sent = Column(Integer)
    tribute_received = Column(Integer)
    trade_gold = Column(Integer)
    relic_gold = Column(Integer)
    technology_score = Column(Integer)
    feudal_time = Column(Interval)
    castle_time = Column(Interval)
    imperial_time = Column(Interval)
    explored_percent = Column(Integer)
    research_count = Column(Integer)
    research_percent = Column(Integer)
    society_score = Column(Integer)
    total_wonders = Column(Integer)
    total_castles = Column(Integer)
    total_relics = Column(Integer)
    villager_high = Column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(['match_id', 'team_id'], ['teams.match_id', 'teams.team_id'], ondelete='cascade'),
        ForeignKeyConstraint(['civilization_id', 'dataset_id'], ['civilizations.id', 'civilizations.dataset_id']),
        ForeignKeyConstraint(['user_id', 'platform_id'], ['users.id', 'users.platform_id']),
    )


class User(BASE):
    """Represents a Platform User."""
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    platform_id = Column(String, ForeignKey('platforms.id'), primary_key=True)
    person_id = Column(Integer, ForeignKey('people.id'), index=True)
    added = Column(DateTime, default=get_utc_now)
    __table_args__ = (
        UniqueConstraint('id', 'platform_id'),
    )


class Ladder(BASE):
    """Represents a platform Ladder."""
    __tablename__ = 'ladders'
    id = Column(Integer, primary_key=True)
    platform_id = Column(String, ForeignKey('platforms.id'), primary_key=True)
    platform = relationship('Platform', foreign_keys=[platform_id], backref='ladders')
    name = Column(String, nullable=False)


class SeriesMetadata(BASE):
    """Represents series metadata."""
    __tablename__ = 'series_metadata'
    id = Column(Integer, primary_key=True)
    series_id = Column(String, ForeignKey('series.id'), index=True)
    series = relationship('Series', foreign_keys=[series_id], backref=backref('metadata', uselist=False))
    name = Column(String)


class Chat(BASE):
    """Represents chat between players."""
    __tablename__ = 'chat'
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    player_number = Column(Integer)
    timestamp = Column(Interval)
    player = relationship('Player', foreign_keys=[match_id, player_number], viewonly=True)
    match = relationship('Match', foreign_keys=[match_id])
    message = Column(String)
    origination = Column(String)
    audience = Column(String)
    __table_args__ = (
        ForeignKeyConstraint(['match_id', 'player_number'], ['players.match_id', 'players.number'], ondelete='cascade'),
    )


class Timeseries(BASE):
    """Represents timeseries data."""
    __tablename__ = 'timeseries'
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    player_number = Column(Integer)
    timestamp = Column(Interval)
    player = relationship('Player', foreign_keys=[match_id, player_number], viewonly=True, backref='chat')
    match = relationship('Match', foreign_keys=[match_id], backref='chat')
    population = Column(Float)
    military = Column(Float)
    percent_explored = Column(Float)
    headroom = Column(Integer)
    food = Column(Integer)
    wood = Column(Integer)
    stone = Column(Integer)
    gold = Column(Integer)
    total_housed_time = Column(Interval)
    total_popcapped_time = Column(Interval)
    relics_captured = Column(Integer)
    relic_gold = Column(Integer)
    trade_profit = Column(Integer)
    tribute_sent = Column(Integer)
    tribute_received = Column(Integer)
    total_food = Column(Integer)
    total_wood = Column(Integer)
    total_stone = Column(Integer)
    total_gold = Column(Integer)
    value_spent_objects = Column(Integer)
    value_spent_research = Column(Integer)
    value_lost_units = Column(Integer)
    value_lost_buildings = Column(Integer)
    value_current_units = Column(Integer)
    value_current_buildings = Column(Integer)
    value_objects_destroyed = Column(Integer)
    value_units_killed = Column(Integer)
    value_buildings_razed = Column(Integer)
    hit_points_razed = Column(Integer)
    hit_points_killed = Column(Integer)
    villager_high = Column(Integer)
    military_high = Column(Integer)
    buildings_lost = Column(Integer)
    kills = Column(Integer)
    razes = Column(Integer)
    deaths = Column(Integer)
    trained = Column(Integer)
    converted = Column(Integer)
    total_score = Column(Integer)
    military_score = Column(Integer)
    economy_score = Column(Integer)
    society_score = Column(Integer)
    technology_score = Column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(['match_id', 'player_number'], ['players.match_id', 'players.number'], ondelete='cascade'),
    )


class Research(BASE):
    """Research."""
    __tablename__ = 'research'
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), index=True)
    dataset = relationship('Dataset', foreign_keys=dataset_id)
    player_number = Column(Integer)
    player = relationship('Player', foreign_keys=[match_id, player_number], viewonly=True, backref='researches')
    match = relationship('Match', foreign_keys=[match_id], backref='researches')
    technology_id = Column(Integer)
    technology = relationship('Technology', foreign_keys=[technology_id, dataset_id], viewonly=True)
    started = Column(Interval)
    finished = Column(Interval)
    __table_args__ = (
        ForeignKeyConstraint(['match_id', 'player_number'], ['players.match_id', 'players.number'], ondelete='cascade'),
        ForeignKeyConstraint(['dataset_id', 'technology_id'], ['technologies.dataset_id', 'technologies.id'])
    )


class ObjectInstance(BASE):
    """Instance of object."""
    __tablename__ = 'object_instances'
    id = Column(Integer, primary_key=True)
    instance_id = Column(Integer, index=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), index=True)
    dataset = relationship('Dataset', foreign_keys=dataset_id)
    initial_player_number = Column(Integer, index=True)
    initial_object_id = Column(Integer, index=True)
    initial_class_id = Column(Integer, index=True)
    states = relationship('ObjectInstanceState', foreign_keys='ObjectInstanceState.match_id', cascade='all, delete, delete-orphan')
    created = Column(Interval)
    destroyed = Column(Interval)
    destroyed_by_instance_id = Column(Integer, index=True)
    deleted = Column(Boolean)
    created_x = Column(Float)
    created_y = Column(Float)
    destroyed_x = Column(Float)
    destroyed_y = Column(Float)
    destroyed_building_percent = Column(Float)
    building_started = Column(Interval)
    building_completed = Column(Interval)
    total_idle_time = Column(Interval)
    __table_args__ = (
        UniqueConstraint('match_id', 'instance_id'),
    )


class ObjectInstanceState(BASE):
    """Instance state."""
    __tablename__ = 'object_instance_states'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Interval)
    instance_id = Column(Integer, index=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), index=True)
    dataset = relationship('Dataset', foreign_keys=dataset_id)
    player_number = Column(Integer)
    player = relationship('Player', foreign_keys=[match_id, player_number], viewonly=True, backref='objects')
    match = relationship('Match', foreign_keys=[match_id], backref='object_states')
    object_id = Column(Integer, index=True)
    object = relationship('Object', foreign_keys=[object_id, dataset_id], viewonly=True)
    class_id = Column(Integer, index=True)
    researching_technology_id = Column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(['match_id', 'player_number'], ['players.match_id', 'players.number'], ondelete='cascade'),
        ForeignKeyConstraint(['dataset_id', 'object_id'], ['objects.dataset_id', 'objects.id']),
        ForeignKeyConstraint(['instance_id', 'match_id'], ['object_instances.instance_id', 'object_instances.match_id'], ondelete='cascade'),
        ForeignKeyConstraint(['dataset_id', 'researching_technology_id'], ['technologies.dataset_id', 'technologies.id'])
    )


class Market(BASE):
    """Market coefficients."""
    __tablename__ = 'market'
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    match = relationship('Match', foreign_keys=[match_id])
    timestamp = Column(Interval)
    wood = Column(Float)
    stone = Column(Float)
    food = Column(Float)


class ActionLog(BASE):
    """Action log."""
    __tablename__ = 'action_log'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Interval, index=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    match = relationship('Match', foreign_keys=[match_id])
    player_number = Column(Integer, index=True)
    action_id = Column(Integer, ForeignKey('actions.id'), index=True)
    action = relationship('Action', foreign_keys=[action_id], viewonly=True)
    action_x = Column(Float)
    action_y = Column(Float)


class Action(BASE):
    """Actions."""
    __tablename__ = 'actions'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class Tribute(BASE):
    """Tribute."""
    __tablename__ = 'tribute'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Interval)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    player_number = Column(Integer, index=True)
    target_player_number = Column(Integer)
    resource_id = Column(Integer, ForeignKey('resources.id'))
    amount = Column(Float)
    fee = Column(Float)


class Transaction(BASE):
    """Market commodity transactions."""
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Interval)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    player_number = Column(Integer, index=True)
    action_id = Column(Integer, ForeignKey('actions.id'))
    resource_id = Column(Integer, ForeignKey('resources.id'))
    amount = Column(Integer)


class Formation(BASE):
    """Formation usage."""
    __tablename__ = 'formations'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Interval)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), index=True)
    player_number = Column(Integer, index=True)
    formation_id = Column(Integer, ForeignKey('formation_types.id'))


class FormationType(BASE):
    """Formation types."""
    __tablename__ = 'formation_types'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class Resource(BASE):
    """Resource."""
    __tablename__ = 'resources'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class Version(BASE):
    """Version."""
    __tablename__ = 'versions'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class HiddenCupPlayers(BASE):
    """HC player."""
    __tablename__ = 'hc'
    hc_name = Column(String, primary_key=True)
    person_name = Column(String, primary_key=True)
    event_id = Column(String)
