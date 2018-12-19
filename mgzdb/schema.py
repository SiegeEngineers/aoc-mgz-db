"""MGZ database schema."""
from datetime import datetime
from sqlalchemy import (
    create_engine, Boolean, DateTime, Column, ForeignKey, Integer, Interval, String
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.schema import UniqueConstraint


BASE = declarative_base()


def get_utc_now():
    """Get current timestamp."""
    return datetime.utcnow()


def get_session(url):
    """Get SQL session."""
    engine = create_engine(url, echo=False)
    session = sessionmaker(bind=engine)()
    BASE.metadata.create_all(engine)
    return session


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
    mod_id = Column(Integer, ForeignKey('mods.id'))
    mod = relationship('Mod', foreign_keys=[mod_id])
    mod_version = Column(String)
    voobly_ladder_id = Column(Integer, ForeignKey('voobly_ladders.id'))
    voobly_ladder = relationship('VooblyLadder', foreign_keys=[voobly_ladder_id])
    players = relationship('Player', back_populates='match', cascade='all, delete-orphan')
    map_id = Column(Integer, ForeignKey('maps.id'))
    map = relationship('Map', foreign_keys=[map_id])
    map_size = Column(String)
    played = Column(DateTime)
    voobly_id = Column(Integer)
    tags = relationship('Tag', foreign_keys='Tag.match_id', cascade='all, delete-orphan')
    duration = Column(Interval)
    completed = Column(Boolean)
    restored = Column(Boolean)
    postgame = Column(Boolean)


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
    match = relationship('Match', foreign_keys=match_id)
    civilization_id = Column(Integer, ForeignKey('civilizations.id'))
    civilization = relationship('Civilization', foreign_keys=[civilization_id])
    human = Column(Boolean)
    rate_before = Column(Integer)
    rate_after = Column(Integer)


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


class Mod(BASE):
    """Represents Mod."""
    __tablename__ = 'mods'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)


class Tag(BASE):
    """Tag."""
    __tablename__ = 'tags'
    name = Column(String, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'), primary_key=True)
    match = relationship('Match', foreign_keys=match_id)


class Tournament(BASE):
    """Represents Tournament."""
    __tablename__ = 'tournaments'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


class Series(BASE):
    """Represents Series."""
    __tablename__ = 'series'
    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey('tournaments.id'))
    tournament = relationship('Tournament', foreign_keys=tournament_id)
    name = Column(String, nullable=False)
    matches = relationship('Match', foreign_keys='Match.series_id', cascade='all, delete-orphan')
    __table_args__ = (UniqueConstraint('tournament_id', 'name', name='unique_series'),)


class VooblyLadder(BASE):
    """Represents Voobly Ladder."""
    __tablename__ = 'voobly_ladders'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class Civilization(BASE):
    """Represent Civilization."""
    __tablename__ = 'civilizations'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class Map(BASE):
    """Represent Map."""
    __tablename__ = 'maps'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    uuid = Column(String, unique=True)
