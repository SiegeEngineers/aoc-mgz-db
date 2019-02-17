"""MGZ database schema."""
from datetime import datetime
from sqlalchemy import (
    create_engine, Boolean, DateTime, Column,
    ForeignKey, Integer, Interval, String
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.schema import ForeignKeyConstraint

from mgzdb.bootstrap import bootstrap


BASE = declarative_base()


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
    bootstrap(session, engine)


def bootstrap_db(url):
    """Bootstrap database."""
    session, engine = get_session(url)
    bootstrap(session, engine)


class File(BASE):
    """Represent File."""
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'))
    match = relationship('Match', foreign_keys=[match_id])
    hash = Column(String, unique=True, nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String)
    size = Column(Integer, nullable=False)
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
    series_id = Column(Integer, ForeignKey('series.id'))
    series = relationship('Series', foreign_keys=series_id)
    files = relationship('File', foreign_keys='File.match_id', cascade='all, delete-orphan')
    version = Column(String)
    minor_version = Column(String)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    dataset_version = Column(String)
    dataset = relationship('Dataset', foreign_keys=dataset_id)
    voobly = Column(Boolean)
    voobly_ladder_id = Column(Integer, ForeignKey('voobly_ladders.id'))
    voobly_ladder = relationship('VooblyLadder', foreign_keys=[voobly_ladder_id])
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
    played = Column(DateTime)
    voobly_id = Column(Integer, unique=True)
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


class Player(BASE):
    """Represent Player in a Match."""
    __tablename__ = 'players'
    match_id = Column(Integer, ForeignKey('matches.id'), primary_key=True)
    number = Column(Integer, nullable=False, primary_key=True)
    color_id = Column(Integer, nullable=False)
    voobly_user_id = Column(Integer, ForeignKey('voobly_users.id'))
    voobly_user = relationship('VooblyUser', foreign_keys=voobly_user_id)
    voobly_clan_id = Column(String, ForeignKey('voobly_clans.id'))
    voobly_clan = relationship('VooblyClan', foreign_keys=voobly_clan_id)
    name = Column(String, nullable=False)
    match = relationship('Match', viewonly=True)
    team_id = Column(Integer)
    team = relationship('Team')
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    dataset = relationship('Dataset', foreign_keys=[dataset_id])
    civilization_id = Column(Integer)
    civilization = relationship('Civilization', back_populates='players', primaryjoin='and_(Player.dataset_id==Civilization.dataset_id, ' \
                                                          'foreign(Player.civilization_id)==Civilization.id)')
    start_x = Column(Integer)
    start_y = Column(Integer)
    human = Column(Boolean)
    winner = Column(Boolean)
    mvp = Column(Boolean)
    score = Column(Integer)
    rate_before = Column(Integer)
    rate_after = Column(Integer)
    __table_args__ = (ForeignKeyConstraint(['match_id', 'team_id'], ['teams.match_id', 'teams.team_id']),
            ForeignKeyConstraint(['civilization_id', 'dataset_id'], ['civilizations.id', 'civilizations.dataset_id']),)


class VooblyUser(BASE):
    """Represents Voobly User."""
    __tablename__ = 'voobly_users'
    id = Column(Integer, primary_key=True)
    matches = relationship('Player', back_populates='voobly_user')


class VooblyClan(BASE):
    """Represents Voobly Clan."""
    __tablename__ = 'voobly_clans'
    id = Column(String, primary_key=True)
    matches = relationship('Player', back_populates='voobly_clan')


class Source(BASE):
    """Represents File Source."""
    __tablename__ = 'sources'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


class Dataset(BASE):
    """Represents a dataset."""
    __tablename__ = 'datasets'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class Tag(BASE):
    """Tag."""
    __tablename__ = 'tags'
    name = Column(String, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'), primary_key=True)
    match = relationship('Match', foreign_keys=match_id)


class Series(BASE):
    """Represents Series."""
    __tablename__ = 'series'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    challonge_id = Column(String, index=True, unique=True)
    matches = relationship('Match', foreign_keys='Match.series_id', cascade='all, delete-orphan')


class VooblyLadder(BASE):
    """Represents Voobly Ladder."""
    __tablename__ = 'voobly_ladders'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class Civilization(BASE):
    """Represent Civilization."""
    __tablename__ = 'civilizations'
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'), primary_key=True)
    dataset = relationship('Dataset', foreign_keys=[dataset_id])
    name = Column(String, nullable=False)
    players = relationship('Player')
    bonuses = relationship('CivilizationBonus', primaryjoin='and_(Civilization.id==foreign(CivilizationBonus.civilization_id), ' \
                                                             'Civilization.dataset_id==CivilizationBonus.dataset_id)')


class CivilizationBonus(BASE):
    __tablename__ = 'civilization_bonuses'
    id = Column(Integer, primary_key=True)
    civilization_id = Column(Integer)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    type = Column(String)
    description = Column(String)


class Map(BASE):
    """Represent Map."""
    __tablename__ = 'maps'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    uuid = Column(String, index=True, unique=True)
