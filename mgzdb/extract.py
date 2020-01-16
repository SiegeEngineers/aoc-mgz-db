"""Record extracted data."""
import logging
from datetime import timedelta

from mgzdb.schema import (
    Chat, Timeseries, Research, ObjectInstance, Market,
    ObjectInstanceState
)


LOGGER = logging.getLogger(__name__)
ALLOWED = False
ALLOWED_LADDERS = [131]
ALLOWED_RATE = 1700


def allow_extraction(players, ladder_id):
    """Check whether extraction should be attempted."""
    rate_sum = sum([p.get('rate_snapshot', 0) for p in players if p.get('rate_snapshot')])
    rate_avg = rate_sum / len(players)
    return ALLOWED and ladder_id in ALLOWED_LADDERS and rate_avg > ALLOWED_RATE


def save_extraction(session, summary, ladder_id, match_id, log_id):
    """Commit extraction data when available."""
    if not summary.can_playback() or not allow_extraction(list(summary.get_players()), ladder_id):
        return False
    LOGGER.info("[m:%s] starting full extraction", log_id)
    try:
        extracted = summary.extract()
    except RuntimeError:
        LOGGER.warning("[m:%s] failed to complete extraction", log_id)
        return False
    objs = []
    for chat in extracted['chat']:
        if chat['type'] != 'chat':
            continue
        del chat['type']
        chat['timestamp'] = timedelta(milliseconds=chat['timestamp'])
        objs.append(Chat(match_id=match_id, **chat))
    for record in extracted['timeseries']:
        record['timestamp'] = timedelta(milliseconds=record['timestamp'])
        objs.append(Timeseries(match_id=match_id, **record))
    for record in extracted['market']:
        record['timestamp'] = timedelta(milliseconds=record['timestamp'])
        objs.append(Market(match_id=match_id, **record))
    for record in extracted['research']:
        record['started'] = timedelta(milliseconds=record['started'])
        record['finished'] = timedelta(milliseconds=record['finished']) if record['finished'] else None
        objs.append(Research(match_id=match_id, dataset_id=dataset_data['id'], **record))
    for record in extracted['objects']:
        record['created'] = timedelta(milliseconds=record['created'])
        record['destroyed'] = timedelta(milliseconds=record['destroyed']) if record['destroyed'] else None
        objs.append(ObjectInstance(match_id=match_id, dataset_id=dataset_data['id'], **record))
    for record in extracted['state']:
        record['timestamp'] = timedelta(milliseconds=record['timestamp'])
        objs.append(ObjectInstanceState(match_id=match_id, dataset_id=dataset_data['id'], **record))
    session.bulk_save_objects(objs)
    session.commit()
    return True
