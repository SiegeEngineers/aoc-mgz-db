"""Record extracted data."""
import logging
from datetime import timedelta

from mgzdb.schema import (
    Timeseries, Research, ObjectInstance, Market,
    ObjectInstanceState
)


LOGGER = logging.getLogger(__name__)
ALLOWED = False
ALLOWED_LADDERS = [131, 132]
ALLOWED_RATE = 0
SUPPORTED_DATASETS = [1]


def allow_extraction(players, ladder_id, dataset_id):
    """Check whether extraction should be attempted."""
    rate_sum = sum([p.get('rate_snapshot', 0) for p in players if p.get('rate_snapshot')])
    rate_avg = rate_sum / len(players)
    return (
        ALLOWED and
        ladder_id in ALLOWED_LADDERS and
        dataset_id in SUPPORTED_DATASETS and
        rate_avg >= ALLOWED_RATE
    )


def save_extraction(session, summary, ladder_id, match_id, dataset_id, log_id, force=False):
    """Commit extraction data when available."""
    if not force and (not summary.can_playback() or not allow_extraction(list(summary.get_players()), ladder_id, dataset_id)):
        LOGGER.info("[m:%s] skipping full extraction, did not meet requirements", log_id)
        return False
    LOGGER.info("[m:%s] starting full extraction", log_id)
    try:
        extracted = summary.extract(1000)
    except RuntimeError as error:
        LOGGER.warning("[m:%s] failed to complete extraction: %s", log_id, error)
        return False
    objs = []
    for record in extracted['timeseries']:
        record['timestamp'] = timedelta(milliseconds=record['timestamp'])
        objs.append(Timeseries(match_id=match_id, **record))
    for record in extracted['market']:
        record['timestamp'] = timedelta(milliseconds=record['timestamp'])
        objs.append(Market(match_id=match_id, **record))
    for record in extracted['research']:
        record['started'] = timedelta(milliseconds=record['started'])
        record['finished'] = timedelta(milliseconds=record['finished']) if record['finished'] else None
        objs.append(Research(match_id=match_id, dataset_id=dataset_id, **record))
    for record in extracted['objects']:
        record['created'] = timedelta(milliseconds=record['created'])
        record['destroyed'] = timedelta(milliseconds=record['destroyed']) if record['destroyed'] else None
        record['building_started'] = timedelta(milliseconds=record['building_started']) if record['building_started'] else None
        record['building_completed'] = timedelta(milliseconds=record['building_completed']) if record['building_completed'] else None
        objs.append(ObjectInstance(match_id=match_id, dataset_id=dataset_id, **record))
    for record in extracted['state']:
        record['timestamp'] = timedelta(milliseconds=record['timestamp'])
        objs.append(ObjectInstanceState(match_id=match_id, dataset_id=dataset_id, **record))
    session.bulk_save_objects(objs)
    session.commit()
    LOGGER.info("[m:%s] completed full extraction", log_id)
    return True
