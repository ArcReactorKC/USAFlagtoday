"""Async client for the documented Mast v1 current-status response.

Schema reference: https://www.mast.today/api (verified 2026-08-27).
Only documented current-status fields are consumed; calendar events are not
assumed to represent the active order.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

from .const import API_KEY_HEADER, API_URL, COUNTRY_CODE, REQUEST_TIMEOUT, STATES


class MastError(Exception):
    """Base error with a safe, non-sensitive message."""


class MastAuthError(MastError):
    """The API rejected authentication."""


class MastConnectionError(MastError):
    """The service could not be reached or is temporarily unavailable."""


class MastLocationError(MastError):
    """The requested location is invalid or not returned by Mast."""


class MastResponseError(MastError):
    """The response does not match the documented schema."""


@dataclass(frozen=True, slots=True)
class MastStatus:
    """Normalized status shared by every entity."""

    is_half_staff: bool
    status: str
    country_code: str
    state_code: str
    reason: str | None = None
    authority: str | None = None
    # Reserved until Mast documents these fields in the current-status object.
    start: datetime | None = None
    end: datetime | None = None
    source_url: str | None = None
    cache_is_stale: bool | None = None


def _optional_text(value: Any) -> str | None:
    """Ignore missing, empty, or incorrectly typed optional text."""
    return value.strip() or None if isinstance(value, str) else None


def parse_status(payload: Any, state_code: str) -> MastStatus:
    """Validate required fields without ever coercing a string to a boolean."""
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise MastResponseError("Mast did not return a successful response")
    status = payload.get("status")
    if not isinstance(status, dict) or type(status.get("isHalfMast")) is not bool:
        raise MastResponseError("Mast returned an invalid status")
    if status.get("countryCode") != COUNTRY_CODE or status.get("stateCode") != state_code:
        raise MastLocationError("Mast did not confirm the requested location")
    half_staff = status["isHalfMast"]
    cache = payload.get("cache")
    stale = cache.get("isStale") if isinstance(cache, dict) else None
    return MastStatus(
        is_half_staff=half_staff,
        status="half_staff" if half_staff else "full_staff",
        country_code=COUNTRY_CODE,
        state_code=state_code,
        reason=_optional_text(status.get("title")),
        authority=_optional_text(status.get("authority")),
        cache_is_stale=stale if type(stale) is bool else None,
    )


class MastClient:
    """Use a caller-owned aiohttp session; never log requests or response bodies."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def async_get_status(self, state_code: str) -> MastStatus:
        """Make exactly one request, with credentials only in the license header."""
        if state_code not in STATES:
            raise MastLocationError("Unsupported U.S. state")
        try:
            async with self._session.get(
                API_URL,
                params={"countryCode": COUNTRY_CODE, "stateCode": state_code},
                headers={API_KEY_HEADER: self._api_key},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise MastAuthError("Mast rejected the API key")
                if response.status in (400, 422):
                    raise MastLocationError("Mast rejected the requested location")
                if response.status == 429 or response.status >= 500:
                    raise MastConnectionError("Mast is temporarily unavailable or rate limited")
                if response.status != 200:
                    raise MastResponseError("Mast returned an unexpected HTTP status")
                try:
                    payload = await response.json()
                except (ValueError, aiohttp.ContentTypeError):
                    raise MastResponseError("Mast returned invalid JSON") from None
        except (aiohttp.ClientError, TimeoutError):
            # Suppress exception chains: aiohttp errors may contain request headers.
            raise MastConnectionError("Unable to communicate with Mast") from None
        return parse_status(payload, state_code)
