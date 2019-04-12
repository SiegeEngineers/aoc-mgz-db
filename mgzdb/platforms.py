"""Platform interface."""

import requests_cache

import aocqq
import voobly

PLATFORM_VOOBLY = 'voobly'
PLATFORM_VOOBLYCN = 'vooblycn'
PLATFORM_QQ = 'qq'
VOOBLY_PLATFORMS = [PLATFORM_VOOBLY, PLATFORM_VOOBLYCN]

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


class VooblySession(PlatformSession):
    """Voobly Platform (global & cn)."""

    def get_match(self, match_id):
        """Get match."""
        return voobly.get_match(self.session, match_id)

    def download_rec(self, url, target):
        """Download a rec."""
        try:
            return voobly.download_rec(self.session, url, target)
        except voobly.VooblyError:
            raise RuntimeError('could not get rec')

    def find_user(self, user_id):
        """Find a user."""
        return voobly.find_user_anon(self.session, user_id)

    def get_ladder_matches(self, ladder_id, from_timestamp=None, limit=None):
        """Get ladder matches."""
        return voobly.get_ladder_matches(self.session, ladder_id, from_timestamp, limit)

    def get_ladder(self, ladder_id, start=0, limit=None):
        """Get ladder ranks."""
        return voobly.get_ladder_anon(self.session, ladder_id, start, limit)

    def get_user_matches(self, user_id, from_timestamp=None, limit=None):
        """Get user matches."""
        return voobly.get_user_matches(self.session, user_id, from_timestamp)

    def get_clan_matches(self, subdomain, clan_id, from_timestamp=None, limit=None):
        """Get clan matches."""
        return voobly.get_clan_matches(self.session, subdomain, clan_id, from_timestamp, limit)


class QQSession(PlatformSession):
    """AoC QQ Platform (aocrec.com)."""

    def get_match(self, match_id):
        """Get a match."""
        return aocqq.get_match(self.session, match_id)

    def download_rec(self, url, target):
        """Download a rec."""
        return aocqq.download_rec(self.session, url, target)

    def get_ladder_matches(self, ladder_id, from_timestamp=None, limit=None):
        """Get ladder matches."""
        return aocqq.get_ladder_matches(self.session, ladder_id, limit)

    def get_ladder(self, ladder_id, start=0, limit=None):
        """Get ladder ranks."""
        return aocqq.get_ladder(self.session, ladder_id, start, limit)

    def get_user_matches(self, user_id, from_timestamp=None, limit=None):
        """Get user matches."""
        return aocqq.get_user_matches(self.session, user_id, limit)


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
    sessions[PLATFORM_QQ] = QQSession(requests_cache.CachedSession(backend='memory'))
    return sessions
