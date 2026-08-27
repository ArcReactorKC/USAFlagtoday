"""Tests against the documented schema; no live credentials required."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.mast_flag.api import (
    MastAuthError,
    MastClient,
    MastConnectionError,
    MastLocationError,
    MastResponseError,
    parse_status,
)
from custom_components.mast_flag.const import API_KEY_HEADER, API_URL


def payload(half=False):
    return {"ok": True, "status": {"countryCode": "US", "stateCode": "MO", "isHalfMast": half}}


@pytest.mark.parametrize("half", [False, True])
def test_status(half):
    result = parse_status(payload(half), "MO")
    assert result.is_half_staff is half
    assert result.status == ("half_staff" if half else "full_staff")
    assert result.reason is None
    assert result.start is result.end is result.source_url is None


def test_optional_fields():
    data = payload(True)
    data["status"].update(title=" Test observance ", authority="Governor")
    data["cache"] = {"isStale": True}
    result = parse_status(data, "MO")
    assert result.reason == "Test observance"
    assert result.authority == "Governor"
    assert result.cache_is_stale is True


@pytest.mark.parametrize("value", [None, {}, [], 1, ""])
def test_bad_optional_fields(value):
    data = payload()
    data["status"].update(title=value, authority=value)
    data["cache"] = value
    assert parse_status(data, "MO").reason is None


@pytest.mark.parametrize("data", [None, [], {}, {"ok": False}, {"ok": True, "status": []}])
def test_malformed(data):
    with pytest.raises(MastResponseError):
        parse_status(data, "MO")


@pytest.mark.parametrize("value", [None, "false", "true", 0, 1, [], {}])
def test_no_boolean_coercion(value):
    data = payload()
    data["status"]["isHalfMast"] = value
    with pytest.raises(MastResponseError):
        parse_status(data, "MO")


@pytest.mark.parametrize(
    "field,value", [("stateCode", "KS"), ("stateCode", None), ("countryCode", "CA")]
)
def test_wrong_location(field, value):
    data = payload()
    data["status"][field] = value
    with pytest.raises(MastLocationError):
        parse_status(data, "MO")


@pytest.mark.parametrize("half", [False, True])
@pytest.mark.parametrize("null_state", [False, True])
def test_location_confirmed_by_calendar(half, null_state):
    """Reproduce the user's live MO response shape, without inventing order data."""
    data = payload(half)
    del data["status"]["stateCode"]
    if null_state:
        data["status"]["stateCode"] = None
    data["calendar"] = {"countryCode": "US", "stateCode": "MO", "events": []}
    result = parse_status(data, "MO")
    assert result.state_code == "MO"
    assert result.is_half_staff is half
    assert result.status == ("half_staff" if half else "full_staff")


@pytest.mark.parametrize(
    "calendar",
    [
        None,
        [],
        {},
        {"events": []},
        {"countryCode": "US"},
        {"stateCode": "MO"},
        {"countryCode": "US", "stateCode": "KS"},
        {"countryCode": "CA", "stateCode": "MO"},
    ],
)
def test_missing_status_location_requires_confirmed_calendar(calendar):
    data = payload(True)
    del data["status"]["stateCode"]
    data["calendar"] = calendar
    with pytest.raises(MastLocationError):
        parse_status(data, "MO")


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("status", "stateCode", "KS"),
        ("status", "stateCode", ""),
        ("status", "countryCode", "CA"),
        ("calendar", "countryCode", "CA"),
        ("calendar", "stateCode", "KS"),
    ],
)
def test_conflicting_location_not_overridden(section, field, value):
    data = payload(True)
    data["calendar"] = {"countryCode": "US", "stateCode": "MO"}
    data[section][field] = value
    with pytest.raises(MastLocationError):
        parse_status(data, "MO")


def session_for(status=200):
    response = MagicMock(status=status)
    response.json = AsyncMock(return_value=payload())
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    session.get.return_value.__aexit__ = AsyncMock(return_value=False)
    return session, response


async def test_request():
    session, _ = session_for()
    result = await MastClient(session, "secret").async_get_status("MO")
    assert result.status == "full_staff"
    session.get.assert_called_once()
    args, kwargs = session.get.call_args
    assert args == (API_URL,)
    assert kwargs["headers"] == {API_KEY_HEADER: "secret"}
    assert kwargs["params"] == {"countryCode": "US", "stateCode": "MO"}
    assert kwargs["allow_redirects"] is False


@pytest.mark.parametrize(
    "status,error",
    [
        (401, MastAuthError),
        (403, MastAuthError),
        (400, MastLocationError),
        (422, MastLocationError),
        (429, MastConnectionError),
        (503, MastConnectionError),
        (302, MastResponseError),
        (404, MastResponseError),
    ],
)
async def test_http_errors(status, error):
    session, _ = session_for(status)
    with pytest.raises(error):
        await MastClient(session, "secret").async_get_status("MO")


@pytest.mark.parametrize("error", [aiohttp.ClientError("secret"), TimeoutError("secret")])
async def test_connection_errors_are_safe(error):
    session, _ = session_for()
    session.get.side_effect = error
    with pytest.raises(MastConnectionError) as exc:
        await MastClient(session, "secret").async_get_status("MO")
    assert "secret" not in str(exc.value)
    assert exc.value.__suppress_context__


async def test_invalid_json():
    session, response = session_for()
    response.json.side_effect = ValueError("secret")
    with pytest.raises(MastResponseError, match="invalid JSON"):
        await MastClient(session, "secret").async_get_status("MO")


async def test_invalid_state_no_request():
    session, _ = session_for()
    with pytest.raises(MastLocationError):
        await MastClient(session, "secret").async_get_status("XX")
    session.get.assert_not_called()
