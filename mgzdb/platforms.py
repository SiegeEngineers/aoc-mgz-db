"""Platform interface."""

try: # private module
    import reliclink
    PLATFORM_RELICLINK = 'de'
except ModuleNotFoundError:
    PLATFORM_RELICLINK = None

import pickle
import os

import aocqq
import voobly

PLATFORM_VOOBLY = 'voobly'
PLATFORM_VOOBLYCN = 'vooblycn'
PLATFORM_IGZ = 'igz'
PLATFORM_QQ = 'qq'
VOOBLY_PLATFORMS = [PLATFORM_VOOBLY, PLATFORM_VOOBLYCN]
QQ_LADDERS = {
    'W': 1
}
RELICLINK_CACHE = 'reliclink_match_cache.pickle'

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


class ReliclinkSession(PlatformSession):

    def download_rec(self, url, target):
        """Download a rec."""
        try:
            return reliclink.download_rec(self.session, url, target)
        except reliclink.ReliclinkError:
            raise RuntimeError('could not get rec')

    def get_match(self, match_id):
        """Use match cache to lookup match data until API endpoint is found."""
        if not os.path.exists(RELICLINK_CACHE):
            raise RuntimeError('no cache')
        with open(RELICLINK_CACHE, 'rb') as handle:
            matches = pickle.load(handle)
        for match in matches:
            if match_id == str(match['match_id']):
                return match
        raise RuntimeError('match not in cache')

    def get_ladder_matches(self, ladder_id, from_timestamp=None, limit=None):
        """Get ladder matches."""
        try:
            matches = reliclink.get_ladder_matches(self.session, ladder_id, from_timestamp, limit)
            with open(RELICLINK_CACHE, 'wb') as handle:
                pickle.dump(matches, handle)
            return matches
        except reliclink.ReliclinkError:
            raise RuntimeError('could not get ladder matches')

    def get_user_matches(self, user_id, from_timestamp=None, limit=None):
        """Get user matches."""
        matches = reliclink.get_user_matches(self.session, user_id, limit)
        with open(RELICLINK_CACHE, 'wb') as handle:
            pickle.dump(matches, handle)
        return matches

    def lookup_ladder_id(self, ladder_name):
        """Lookup ladder ID."""
        return reliclink.lookup_ladder_id(ladder_name)


def factory(voobly_key=None, voobly_username=None, voobly_password=None,
            reliclink_username=None, reliclink_password=None, reliclink_session_id=None):
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
    if PLATFORM_RELICLINK:
        sessions[PLATFORM_RELICLINK] = ReliclinkSession(reliclink.get_session(
            username=reliclink_username,
            password=reliclink_password,
            session_id=reliclink_session_id
        ))
    return sessions
