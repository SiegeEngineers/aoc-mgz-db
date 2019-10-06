"""MGZ database schema."""

from sqlalchemy import (
    create_engine, Boolean, DateTime, Column,
    ForeignKey, Integer, Interval, String, Float
)
from sqlalchemy.orm import relationship, sessionmaker, backref
from sqlalchemy.schema import ForeignKeyConstraint, UniqueConstraint

from aocref.bootstrap import bootstrap
from aocref.model import BASE

from mgzdb.util import get_utc_now


def get_session(url):
    """Get SQL session."""
    engine = create_engine(url, echo=False)
    session = sessionmaker(bind=engine)()
    return session, engine


def reset(url):
    """Reset database - use with caution."""
    session, engine = get_session(url)
    BASE.metadata.drop_all(engine)
    BASE.metadata.create_all(engine)
    bootstrap(session)


class File(BASE):
    """Represent File."""
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'))
    match = relationship('Match', foreign_keys=[match_id])
    hash = Column(String, unique=True, nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String)
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
    series_id = Column(String, ForeignKey('series.id'))
    tournament_id = Column(String, ForeignKey('tournaments.id'))
    event_id = Column(String, ForeignKey('events.id'))
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
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    dataset_version = Column(String)
    dataset = relationship('Dataset', foreign_keys=dataset_id)
    platform_id = Column(String, ForeignKey('platforms.id'))
    platform = relationship('Platform', foreign_keys=platform_id)
    ladder_id = Column(Integer)
    ladder = relationship('Ladder', foreign_keys=[ladder_id, platform_id], viewonly=True)
    rated = Column(Boolean)
    builtin_map_id = Column(Integer)
    builtin_map = relationship('Map', foreign_keys=[builtin_map_id, dataset_id], backref='matches', viewonly=True)
    map_size_id = Column(Integer, ForeignKey('map_sizes.id'))
    map_size = relationship('MapSize', foreign_keys=map_size_id)
    map_name = Column(String, index=True)
    event_map_id = Column(Integer, ForeignKey('event_maps.id'))
    event_map = relationship('EventMap', foreign_keys=event_map_id, backref='matches')
    rms_zr = Column(Boolean)
    rms_custom = Column(Boolean)
    rms_seed = Column(Integer)
    guard_state = Column(Boolean)
    fixed_positions = Column(Boolean)
    direct_placement = Column(Boolean)
    effect_quantity = Column(Boolean)
    played = Column(DateTime, index=True)
    added = Column(DateTime, default=get_utc_now)
    platform_match_id = Column(Integer, unique=True)
    duration = Column(Interval)
    completed = Column(Boolean)
    restored = Column(Boolean)
    postgame = Column(Boolean)
    type_id = Column(Integer, ForeignKey('game_types.id'))
    type = relationship('GameType', foreign_keys=type_id)
    difficulty_id = Column(Integer, ForeignKey('difficulties.id'))
    difficulty = relationship('Difficulty', foreign_keys=difficulty_id)
    population_limit = Column(Integer)
    map_reveal_choice_id = Column(Integer, ForeignKey('map_reveal_choices.id'))
    map_reveal_choice = relationship('MapRevealChoice', foreign_keys=map_reveal_choice_id)
    cheats = Column(Boolean)
    speed_id = Column(Integer, ForeignKey('speeds.id'))
    speed = relationship('Speed', foreign_keys=speed_id)
    lock_teams = Column(Boolean)
    mirror = Column(Boolean)
    diplomacy_type = Column(String, nullable=False, index=True)
    team_size = Column(String, nullable=False, index=True)
    starting_resources_id = Column(Integer, ForeignKey('starting_resources.id'))
    starting_resources = relationship('StartingResources', foreign_keys=starting_resources_id)
    starting_age_id = Column(Integer, ForeignKey('starting_ages.id'))
    starting_age = relationship('StartingAge', foreign_keys=starting_age_id)
    victory_condition_id = Column(Integer, ForeignKey('victory_conditions.id'))
    victory_condition = relationship('VictoryCondition', foreign_keys=victory_condition_id)
    team_together = Column(Boolean)
    all_technologies = Column(Boolean)
    lock_speed = Column(Boolean)
    multiqueue = Column(Boolean)
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
    match_id = Column(Integer, ForeignKey('matches.id', ondelete='cascade'), primary_key=True)
    name = Column(String, nullable=False)
    number = Column(Integer, nullable=False, primary_key=True)
    color_id = Column(Integer, ForeignKey('player_colors.id'), nullable=False)
    color = relationship('PlayerColor', foreign_keys=color_id)
    platform_id = Column(String, ForeignKey('platforms.id'))
    platform = relationship('Platform', foreign_keys=platform_id)
    user_id = Column(String, index=True)
    user_name = Column(String, index=True)
    user = relationship('User', foreign_keys=[user_id, platform_id], viewonly=True)
    match = relationship('Match', foreign_keys=[match_id], viewonly=True)
    team_id = Column(Integer)
    team = relationship('Team', foreign_keys=[match_id, team_id], backref='members', viewonly=True, cascade='all, delete, delete-orphan', single_parent=True, post_update=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    dataset = relationship('Dataset', foreign_keys=[dataset_id])
    civilization_id = Column(Integer, index=True)
    civilization = relationship('Civilization', foreign_keys=[dataset_id, civilization_id], backref='players', viewonly=True)
    start_x = Column(Integer)
    start_y = Column(Integer)
    human = Column(Boolean)
    winner = Column(Boolean)
    mvp = Column(Boolean)
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
        ForeignKeyConstraint(['user_id', 'platform_id'], ['users.id', 'users.platform_id'])
    )


class User(BASE):
    """Represents a Platform User."""
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    platform_id = Column(String, ForeignKey('platforms.id'), primary_key=True)
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
    series_id = Column(String, ForeignKey('series.id'))
    series = relationship('Series', foreign_keys=[series_id], backref=backref('metadata', uselist=False))
    name = Column(String)
