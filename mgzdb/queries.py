"""MGZ database queries."""
import logging

from sqlalchemy import func
from mgzdb.schema import (
    File, Match, Series, VooblyLadder, Source,
    Mod, Civilization, Map, VooblyUser, Tag
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
        'series': session.query(Series).count(),
        'ladders': _group_by_relation(session, VooblyLadder.name, Match, Match.voobly_ladder_id),
        'sources': _group_by_relation(session, Source.name, File, File.source_id),
        'tags': session.query(Tag).count(),
        'mods': _group_by_relation(session, Mod.name, Match, Match.mod_id),
        'civilizations': session.query(Civilization).count(),
        'maps': session.query(Map).count(),
        'versions': _group_by(session, Match.version),
        'voobly_users': session.query(VooblyUser).count(),
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
            'voobly_id': mgz.owner.voobly_user.id if mgz.owner.voobly_user else None
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
        'voobly_id': match.voobly_id,
        'played': str(match.played),
        'files': [{
            'filename': f.filename,
            'original': f.original_filename,
            'owner': {
                'name': f.owner.name,
                'voobly_id': f.owner.voobly_user.id if f.owner.voobly_user else None
            },
            'source': f.source.name,
            'reference': f.reference,
            'added': str(f.added)
        } for f in match.files],
        'series': {
            'name': match.series.name if match.series else None
        },
        'tags': [t.name for t in match.tags],
        'version': {
            'major': match.version,
            'minor': match.minor_version,
            'mod': {
                'name': match.mod.name,
                'version': match.mod_version
            } if match.mod else None
        },
        'ladder': match.voobly_ladder.name if match.voobly_ladder else None,
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
            'voobly_id': p.voobly_user.id if p.voobly_user else None,
            'voobly_clan': p.voobly_clan.id if p.voobly_clan else None,
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
