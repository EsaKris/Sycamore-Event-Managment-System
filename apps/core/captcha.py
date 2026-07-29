"""
hCaptcha server-side verification for the public registration forms.
Deliberately built on stdlib urllib rather than adding `requests` as a new
project dependency — this is the only outbound HTTP call the app makes
server-side, so it isn't worth the extra package.
"""

import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = 'https://hcaptcha.com/siteverify'
TIMEOUT_SECONDS = 6


def is_configured() -> bool:
    return bool(settings.HCAPTCHA_SECRET_KEY and settings.HCAPTCHA_SITE_KEY)


def verify_hcaptcha(token: str, remote_ip: str = '') -> bool:
    """
    Verifies an 'h-captcha-response' token against hCaptcha's API.

    Fails OPEN (returns True) when HCAPTCHA keys aren't configured — so
    local dev and any deployment that hasn't set up hCaptcha yet keeps
    working off the existing honeypot + rate limit, with a warning logged
    rather than silently blocking every public registration.

    Fails CLOSED (returns False) on a missing token, a verification
    failure reported by hCaptcha, or a network/timeout error talking to
    hCaptcha — a real outage there should not be treated as "let everyone
    through".
    """
    if not is_configured():
        logger.warning('hCaptcha is not configured (HCAPTCHA_SITE_KEY/HCAPTCHA_SECRET_KEY unset) — skipping verification.')
        return True

    if not token:
        return False

    data = {'secret': settings.HCAPTCHA_SECRET_KEY, 'response': token}
    if remote_ip:
        data['remoteip'] = remote_ip

    try:
        req = urllib.request.Request(
            VERIFY_URL,
            data=urllib.parse.urlencode(data).encode('utf-8'),
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        return bool(result.get('success'))
    except Exception:
        logger.exception('hCaptcha verification request failed')
        return False
