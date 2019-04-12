"""MGZ database queries."""
import logging

from sqlalchemy import func
from aocref.model import Series, Dataset, Civilization
from mgzdb.schema import (
    File, Match, User, SeriesMetadata
)


LOGGER = logging.getLogger(__name__)


def _group_by(session, field):
    """Group by a field."""
    return dict(session.query(field, func.count(field)).group_by(field).all())


def _group_by_relation(session, field, relation, relation_field):
    """Group by a relation field."""
    return dict(session.query(field, func.count(relation_field)).join(relation).group_by(field, relation_field).all())


def get_summary(session):
    """Summarize holdings."""
    return {
        'files': session.query(File).count(),
        'matches': session.query(Match).count(),
        'series': session.query(SeriesMetadata).count(),
        'datasets': _group_by_relation(session, Dataset.name, Match, Match.dataset_id),
        'civilizations': session.query(Civilization).count(),
        'maps': _group_by(session, Match.map_name),
        'versions': _group_by(session, Match.version),
        'users': session.query(User).count()
    }


def get_file(session, file_id):
    """Look up a file."""
    mgz = session.query(File).get(file_id)
    if not mgz:
        LOGGER.error("file %d does not exist", file_id)
        return None
    return {
        'file_id': file_id,
        'filename': mgz.filename,
        'original': mgz.original_filename,
        'owner': {
            'name': mgz.owner.name,
            'user_id': mgz.owner.user.id if mgz.owner.user else None
        },
        'source': mgz.source.name,
        'reference': mgz.reference,
        'added': str(mgz.added),
        'parser_version': mgz.parser_version
    }


def get_series(session, series_id):
    """Look up series."""
    series = session.query(Series).get(series_id)
    if not series:
        LOGGER.error("series %d does not exist", series_id)
        return None
    return {
        'series_id': series_id,
        'challonge_id': series.challonge_id,
        'name': series.name,
        'matches': [{
            'match_id': match.id,
            'files': [{
                'file_id': mgz.id,
                'filename': mgz.filename,
                'original': mgz.original_filename
            } for mgz in match.files]
        } for match in series.matches]
    }


def get_match(session, match_id):
    """Look up a match."""
    match = session.query(Match).get(match_id)
    if not match:
        LOGGER.error("match %d does not exist", match_id)
        return None
    return {
        'match_id': match_id,
        'platform_id': match.platform_id,
        'platform_match_id': match.platform_match_id,
        'played': str(match.played),
        'files': [{
            'filename': f.filename,
            'original': f.original_filename,
            'owner': {
                'name': f.owner.name,
                'user_id': f.owner.user.id if f.owner.user else None
            },
            'source': f.source.name,
            'reference': f.reference,
            'added': str(f.added)
        } for f in match.files],
        'series': {
            'name': match.series.name if match.series else None
        },
        'version': {
            'major': match.version,
            'minor': match.minor_version,
            'dataset': {
                'name': match.dataset.name,
                'version': match.dataset_version
            } if match.dataset else None
        },
        'map': {
            'name': match.map.name,
            'size': match.map_size
        },
        'duration': str(match.duration),
        'completed': match.completed,
        'postgame': match.postgame,
        'restored': match.restored,
        'players': [{
            'name': p.name,
            'number': p.number,
            'user_id': p.user.id if p.user else None,
            'civilization': p.civilization.name,
            'human': p.human,
            'score': p.score,
            'mvp': p.mvp,
            'rate': {
                'before': p.rate_before,
                'after': p.rate_after
            },
        } for p in match.players],
        'teams': [[m.name for m in t.members] for t in match.teams],
        'winners': [t.name for t in match.winning_team]
    }
