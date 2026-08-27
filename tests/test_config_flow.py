"""Exercise real Home Assistant flow handlers using mocked API calls."""

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.mast_flag.api import (
    MastAuthError,
    MastConnectionError,
    MastLocationError,
    MastResponseError,
    parse_status,
)
from tests.test_api import payload, session_for

CLIENT = "custom_components.mast_flag.api.MastClient.async_get_status"
INPUT = {"api_key": "test-key", "country_code": "US", "state_code": "MO"}


async def test_user_success(hass):
    result = await hass.config_entries.flow.async_init("mast_flag", context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with (
        patch(CLIENT, return_value=parse_status(payload(), "MO")),
        patch("custom_components.mast_flag.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == INPUT
    assert result["result"].unique_id == "US_MO"


async def test_user_success_with_live_calendar_location(hass):
    """Exercise the actual client/parser in setup with the reported response shape."""
    session, response = session_for()
    data = payload(True)
    del data["status"]["stateCode"]
    data["calendar"] = {"countryCode": "US", "stateCode": "MO", "events": []}
    response.json.return_value = data
    with (
        patch(
            "custom_components.mast_flag.config_flow.async_get_clientsession", return_value=session
        ),
        patch("custom_components.mast_flag.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            "mast_flag", context={"source": SOURCE_USER}, data=INPUT
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "US_MO"
    session.get.assert_called_once()


@pytest.mark.parametrize(
    "error,expected",
    [
        (MastAuthError, "invalid_auth"),
        (MastConnectionError, "cannot_connect"),
        (MastLocationError, "invalid_location"),
        (MastResponseError, "invalid_response"),
    ],
)
async def test_user_errors(hass, error, expected):
    with patch(CLIENT, side_effect=error):
        result = await hass.config_entries.flow.async_init(
            "mast_flag",
            context={"source": SOURCE_USER},
            data=INPUT,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    assert not hass.config_entries.async_entries("mast_flag")


async def test_duplicate(hass, entry):
    with patch(CLIENT, return_value=parse_status(payload(), "MO")):
        result = await hass.config_entries.flow.async_init(
            "mast_flag",
            context={"source": SOURCE_USER},
            data=INPUT,
        )
    assert result["reason"] == "already_configured"


async def test_reauth(hass, entry):
    result = await hass.config_entries.flow.async_init(
        "mast_flag",
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    with (
        patch(CLIENT, return_value=parse_status(payload(), "MO")),
        patch("homeassistant.config_entries.ConfigEntries.async_reload", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "replacement-key"},
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert entry.data["api_key"] == "replacement-key"
    assert entry.unique_id == "US_MO"
    assert len(hass.config_entries.async_entries("mast_flag")) == 1


async def test_options(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    data = payload()
    data["status"]["stateCode"] = "KS"
    with (
        patch(CLIENT, return_value=parse_status(data, "KS")) as request,
        patch("homeassistant.config_entries.ConfigEntries.async_reload", return_value=True),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"state_code": "KS"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    request.assert_awaited_once_with("KS")
    assert entry.options["state_code"] == "KS"
    assert entry.unique_id == "US_KS"
    assert entry.title == "Mast Flag Status - Kansas"


async def test_options_failure_preserves_entry(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(CLIENT, side_effect=MastLocationError):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"state_code": "KS"},
        )
    assert result["errors"] == {"base": "invalid_location"}
    assert entry.options == {}
    assert entry.unique_id == "US_MO"


async def test_reauth_rejects_invalid_key(hass, entry):
    result = await hass.config_entries.flow.async_init(
        "mast_flag",
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    with patch(CLIENT, side_effect=MastAuthError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "invalid-replacement"},
        )
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["api_key"] == "test-key"


async def test_options_duplicate(hass, entry):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    other = MockConfigEntry(
        domain="mast_flag",
        unique_id="US_KS",
        data={"api_key": "another-key", "country_code": "US", "state_code": "KS"},
    )
    other.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    data = payload()
    data["status"]["stateCode"] = "KS"
    with patch(CLIENT, return_value=parse_status(data, "KS")):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"state_code": "KS"},
        )
    assert result["errors"] == {"base": "already_configured"}
    assert entry.unique_id == "US_MO"
    assert entry.options == {}
