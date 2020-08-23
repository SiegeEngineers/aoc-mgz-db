"""Platform interface."""

import pickle
import os

import aocqq
import aoeapi
import voobly

PLATFORM_VOOBLY = 'voobly'
PLATFORM_VOOBLYCN = 'vooblycn'
PLATFORM_IGZ = 'igz'
PLATFORM_QQ = 'qq'
PLATFORM_DE = 'de'
VOOBLY_PLATFORMS = [PLATFORM_VOOBLY, PLATFORM_VOOBLYCN]
QQ_LADDERS = {
    'W': 1
}
AOEAPI_CACHE = 'aoeapi_match_cache.pickle'

# pylint: disable=abstract-method

class PlatformSession():
    """Platform abstract class.

    All platforms supported by MGZ DB must conform to this interface.
    """

    def __init__(self, session):
        """Initialize."""
        self.session = session

    def get_match(self, match_id):
        """Get a match."""
        raise NotImplementedError()

    def download_rec(self, url, target):
        """Download a rec."""
        raise NotImplementedError()

    def find_user(self, user_id):
        """Find a user."""
        raise NotImplementedError()

    def get_ladder_matches(self, ladder_id, from_timestamp=None, limit=None):
        """Get ladder matches."""
        raise NotImplementedError()

    def get_ladder(self, ladder_id, start=0, limit=None):
        """Get ladder ranks."""
        raise NotImplementedError()

    def get_user_matches(self, user_id, from_timestamp=None, limit=None):
        """Get user matches."""
        raise NotImplementedError()

    def get_clan_matches(self, subdomain, clan_id, from_timestamp=None, limit=None):
        """Get clan matches."""
        raise NotImplementedError()

    def lookup_ladder_id(self, ladder_name):
        """Get ladder ID."""
        raise NotImplementedError()


class VooblySession(PlatformSession):
    """Voobly Platform (global & cn)."""

    def get_match(self, match_id):
        """Get match."""
        try:
            return voobly.get_match(self.session, match_id)
        except voobly.VooblyError:
            raise RuntimeError('could not get match')

    def download_rec(self, url, target):
        """Download a rec."""
        try:
            return voobly.download_rec(self.session, url, target)
        except voobly.VooblyError:
            raise RuntimeError('could not get rec')

    def find_user(self, user_id):
        """Find a user."""
        try:
            return voobly.find_user_anon(self.session, user_id)
        except voobly.VooblyError:
            raise RuntimeError('could not find user')

    def get_ladder_matches(self, ladder_id, from_timestamp=None, limit=None):
        """Get ladder matches."""
        try:
            return voobly.get_ladder_matches(self.session, ladder_id, from_timestamp, limit)
        except voobly.VooblyError:
            raise RuntimeError('could not get ladder')

    def get_ladder(self, ladder_id, start=0, limit=None):
        """Get ladder ranks."""
        return voobly.get_ladder_anon(self.session, ladder_id, start, limit)

    def get_user_matches(self, user_id, from_timestamp=None, limit=None):
        """Get user matches."""
        return voobly.get_user_matches(self.session, user_id, from_timestamp)

    def get_clan_matches(self, subdomain, clan_id, from_timestamp=None, limit=None):
        """Get clan matches."""
        return voobly.get_clan_matches(self.session, subdomain, clan_id, from_timestamp, limit)

    def lookup_ladder_id(self, ladder_name):
        """Lookup ladder ID."""
        return voobly.lookup_ladder_id(ladder_name)


class QQSession(PlatformSession):
    """AoC QQ Platform (aocrec.com)."""

    def get_match(self, match_id):
        """Get a match."""
        try:
            return aocqq.get_match(self.session, match_id)
        except aocqq.AOCQQError:
            raise RuntimeError('could not get match')

    def download_rec(self, url, target):
        """Download a rec."""
        try:
            return aocqq.download_rec(self.session, url, target)
        except aocqq.AOCQQError:
            raise RuntimeError('could not get rec')

    def get_ladder_matches(self, ladder_id, from_timestamp=None, limit=None):
        """Get ladder matches."""
        try:
            return aocqq.get_ladder_matches(self.session, ladder_id, limit)
        except aocqq.AOCQQError:
            raise RuntimeError('could not get ladder matches')

    def get_ladder(self, ladder_id, start=0, limit=None):
        """Get ladder ranks."""
        return aocqq.get_ladder(self.session, ladder_id, start, limit)

    def get_user_matches(self, user_id, from_timestamp=None, limit=None):
        """Get user matches."""
        return aocqq.get_user_matches(self.session, user_id, limit)

    def lookup_ladder_id(self, ladder_name):
        """Lookup ladder ID."""
        try:
            return QQ_LADDERS[ladder_name]
        except KeyError:
            raise ValueError('could not find ladder id')


class DefinitiveSession(PlatformSession):

    def download_rec(self, url, target):
        """Download a rec."""
        try:
            return aoeapi.download_rec(url, target)
        except aoeapi.AoeApiError:
            raise RuntimeError('could not get rec')

    def get_match(self, match_id):
        """Use match cache to lookup profile ID."""
        if not os.path.exists(AOEAPI_CACHE):
            raise RuntimeError('no cache')
        with open(AOEAPI_CACHE, 'rb') as handle:
            matches = pickle.load(handle)
        for match in matches:
            if match_id == match['match_id']:
                return aoeapi.get_match(match['ref_profile_id'], match_id)
        raise RuntimeError('match not in cache')

    def get_ladder_matches(self, ladder_id, from_timestamp=None, limit=None):
        """Get ladder matches."""
        try:
            matches = aoeapi.get_ladder_matches(ladder_id, from_timestamp, limit)
            with open(AOEAPI_CACHE, 'rb') as handle:
                cached_matches = pickle.load(handle)
            with open(AOEAPI_CACHE, 'wb') as handle:
                pickle.dump(cached_matches + matches, handle)
            return matches
        except aoeapi.AoeApiError:
            raise RuntimeError('could not get ladder matches')

    def get_user_matches(self, user_id, from_timestamp=None, limit=None):
        """Get user matches."""
        matches = aoeapi.get_user_matches(user_id, limit)
        with open(AOEAPI_CACHE, 'rb') as handle:
            cached_matches = pickle.load(handle)
        with open(AOEAPI_CACHE, 'wb') as handle:
            pickle.dump(cached_matches + matches, handle)
        return matches

    def lookup_ladder_id(self, ladder_name):
        """Lookup ladder ID."""
        return aoeapi.lookup_ladder_id(ladder_name)


def factory(voobly_key=None, voobly_username=None, voobly_password=None):
    """Platform session factory.

    Produce a session for all supported platforms.
    """
    sessions = {}
    sessions.update({id:VooblySession(voobly.get_session(
        key=voobly_key,
        username=voobly_username,
        password=voobly_password,
        version=id
    )) for id in VOOBLY_PLATFORMS})
    sessions[PLATFORM_QQ] = QQSession(aocqq.get_session())
    sessions[PLATFORM_IGZ] = sessions[PLATFORM_VOOBLY]
    sessions[PLATFORM_DE] = DefinitiveSession(None)
    return sessions
