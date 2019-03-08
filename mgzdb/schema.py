"""MGZ database schema."""

from datetime import datetime
from sqlalchemy import (
    create_engine, Boolean, DateTime, Column,
    ForeignKey, Integer, Interval, String, Float
)
from sqlalchemy.orm import relationship, sessionmaker, backref
from sqlalchemy.schema import ForeignKeyConstraint

from aocref.bootstrap import bootstrap
from aocref.model import BASE


def get_utc_now():
    """Get current timestamp."""
    return datetime.utcnow()


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


def bootstrap_db(url):
    """Bootstrap database."""
    session, _ = get_session(url)
    bootstrap(session)


class File(BASE):
    """Represent File."""
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'))
    match = relationship('Match', foreign_keys=[match_id])
    hash = Column(String, unique=True, nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String)
    encoding = Column(String)
    language = Column(String)
    size = Column(Integer, nullable=False)
    compressed_size = Column(Integer, nullable=False)
    owner_number = Column(Integer, nullable=False)
    owner = relationship('Player', primaryjoin='and_(File.match_id==Player.match_id, ' \
                                                    'foreign(File.owner_number)==Player.number)')
    source_id = Column(Integer, ForeignKey('sources.id'))
    source = relationship('Source', foreign_keys=[source_id])
    reference = Column(String)
    added = Column(DateTime, default=get_utc_now)
    parser_version = Column(String, nullable=False)


class Team(BASE):
    """Represent a team."""
    __tablename__ = 'teams'
    team_id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'), primary_key=True)
    winner = Column(Boolean)
    match = relationship('Match', foreign_keys=match_id)
    members = relationship('Player', primaryjoin='and_(Team.match_id==Player.match_id, ' \
                                                 'Team.team_id==Player.team_id)')


class Match(BASE):
    """Represents Match."""
    __tablename__ = 'matches'
    id = Column(Integer, primary_key=True)
    hash = Column(String, unique=True)
    series_id = Column(String, ForeignKey('series.id'))
    series = relationship('Series', foreign_keys=series_id, backref='matches')
    files = relationship('File', foreign_keys='File.match_id', cascade='all, delete-orphan')
    version = Column(String)
    minor_version = Column(String)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    dataset_version = Column(String)
    dataset = relationship('Dataset', foreign_keys=dataset_id)
    platform_id = Column(String, ForeignKey('platforms.id'))
    platform = relationship('Platform', foreign_keys=platform_id)
    ladder_id = Column(Integer, ForeignKey('ladders.id'))
    ladder = relationship('Ladder', primaryjoin='and_(foreign(Match.platform_id)==Ladder.platform_id, ' \
                                                'foreign(Match.ladder_id)==Ladder.id)')
    rated = Column(Boolean)
    players = relationship('Player', back_populates='match', cascade='all, delete-orphan')
    teams = relationship('Team', foreign_keys='Team.match_id', cascade='all, delete-orphan')
    winning_team_id = Column(Integer)
    winning_team = relationship('Player', primaryjoin='and_(Player.match_id==Match.id, ' \
                                                      'Player.team_id==Match.winning_team_id)')
    losers = relationship('Player', primaryjoin='and_(Player.match_id==Match.id, ' \
                                                'Player.team_id!=Match.winning_team_id)')
    map_id = Column(Integer, ForeignKey('maps.id'))
    map = relationship('Map', foreign_keys=[map_id])
    map_size = Column(String)
    map_seed = Column(Integer)
    played = Column(DateTime)
    added = Column(DateTime, default=get_utc_now)
    platform_match_id = Column(Integer, unique=True)
    tags = relationship('Tag', foreign_keys='Tag.match_id', cascade='all, delete-orphan')
    duration = Column(Interval)
    completed = Column(Boolean)
    restored = Column(Boolean)
    postgame = Column(Boolean)
    type = Column(String)
    difficulty = Column(String)
    population_limit = Column(Integer)
    reveal_map = Column(String)
    cheats = Column(Boolean)
    speed = Column(String)
    lock_teams = Column(Boolean)
    mirror = Column(Boolean)
    diplomacy_type = Column(String, nullable=False)
    team_size = Column(String)
    starting_resources = Column(String)
    starting_age = Column(String)
    victory_condition = Column(String)
    team_together = Column(Boolean)
    all_technologies = Column(Boolean)
    lock_speed = Column(Boolean)
    multiqueue = Column(Boolean)


class Player(BASE):
    """Represent Player in a Match."""
    __tablename__ = 'players'
    match_id = Column(Integer, ForeignKey('matches.id'), primary_key=True)
    number = Column(Integer, nullable=False, primary_key=True)
    color_id = Column(Integer, nullable=False)

    platform_id = Column(String, ForeignKey('platforms.id'))
    platform = relationship('Platform', foreign_keys=platform_id)
    user_id = Column(String, ForeignKey('users.id'))
    user = relationship('User', primaryjoin='and_(Player.platform_id==User.platform_id, ' \
                                                'foreign(Player.user_id)==User.id)')
    name = Column(String, nullable=False)
    match = relationship('Match', viewonly=True)
    team_id = Column(Integer)
    team = relationship('Team')
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    dataset = relationship('Dataset', foreign_keys=[dataset_id])
    civilization_id = Column(Integer)
    civilization = relationship('Civilization', backref='players', primaryjoin='and_(Player.dataset_id==Civilization.dataset_id, ' \
                                                          'foreign(Player.civilization_id)==Civilization.id)')
    start_x = Column(Integer)
    start_y = Column(Integer)
    human = Column(Boolean)
    winner = Column(Boolean)
    mvp = Column(Boolean)
    score = Column(Integer)
    rate_before = Column(Float)
    rate_after = Column(Float)
    rate_snapshot = Column(Float)
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
        ForeignKeyConstraint(['match_id', 'team_id'], ['teams.match_id', 'teams.team_id']),
        ForeignKeyConstraint(['civilization_id', 'dataset_id'], ['civilizations.id', 'civilizations.dataset_id'])
    )


class User(BASE):
    """Represents a Platform User."""
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    platform_id = Column(String, ForeignKey('platforms.id'), primary_key=True)


class Source(BASE):
    """Represents File Source."""
    __tablename__ = 'sources'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


class Tag(BASE):
    """Tag."""
    __tablename__ = 'tags'
    name = Column(String, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'), primary_key=True)
    match = relationship('Match', foreign_keys=match_id)


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


class Map(BASE):
    """Represent Map."""
    __tablename__ = 'maps'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
