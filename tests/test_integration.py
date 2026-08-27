"""Setup, shared polling, availability, identity, and unload tests."""

from unittest.mock import patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.mast_flag.api import MastAuthError, MastConnectionError, parse_status
from custom_components.mast_flag.const import UPDATE_INTERVAL
from custom_components.mast_flag.coordinator import MastCoordinator
from tests.test_api import payload

CLIENT = "custom_components.mast_flag.api.MastClient.async_get_status"


@pytest.mark.parametrize("half", [True, False])
async def test_setup_and_unload(hass, entry, half):
    data = payload(half)
    data["status"]["title"] = "Example observance"
    with patch(CLIENT, return_value=parse_status(data, "MO")) as request:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        request.assert_awaited_once_with("MO")
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 3
    states = {
        entity.unique_id.removeprefix(f"{entry.entry_id}_"): hass.states.get(entity.entity_id)
        for entity in entities
    }
    assert states["flag_half_staff"].state == ("on" if half else "off")
    assert states["flag_status"].state == ("half_staff" if half else "full_staff")
    assert states["flag_status_reason"].state == "Example observance"
    assert states["flag_status"].attributes["state_code"] == "MO"
    assert len({entity.device_id for entity in entities}) == 1
    assert entry.runtime_data.update_interval == UPDATE_INTERVAL
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_availability_recovers(hass, entry):
    with patch(CLIENT, return_value=parse_status(payload(), "MO")):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    with patch(CLIENT, side_effect=MastConnectionError("Service unavailable")):
        await entry.runtime_data.async_refresh()
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert all(hass.states.get(entity.entity_id).state == "unavailable" for entity in entities)
    with patch(CLIENT, return_value=parse_status(payload(True), "MO")):
        await entry.runtime_data.async_refresh()
    assert entry.runtime_data.last_update_success
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "error,expected", [(MastAuthError, ConfigEntryAuthFailed), (MastConnectionError, UpdateFailed)]
)
async def test_coordinator_errors(hass, entry, error, expected):
    coordinator = MastCoordinator(hass, entry)
    with patch(CLIENT, side_effect=error), pytest.raises(expected):
        await coordinator._async_update_data()


async def test_reason_limit_and_unknown(hass, entry):
    data = payload(True)
    data["status"]["title"] = "x" * 300
    with patch(CLIENT, return_value=parse_status(data, "MO")):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", "mast_flag", f"{entry.entry_id}_flag_status_reason"
    )
    assert len(hass.states.get(entity_id).state) == 255
    assert len(hass.states.get(entity_id).attributes["reason"]) == 300
    with patch(CLIENT, return_value=parse_status(payload(), "MO")):
        await entry.runtime_data.async_refresh()
    assert hass.states.get(entity_id).state == "unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_reload_preserves_identity(hass, entry):
    with patch(CLIENT, return_value=parse_status(payload(), "MO")):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    registry = er.async_get(hass)
    before = er.async_entries_for_config_entry(registry, entry.entry_id)
    data = payload()
    data["status"]["stateCode"] = "KS"
    with patch(CLIENT, return_value=parse_status(data, "KS")):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(flow["flow_id"], {"state_code": "KS"})
        await hass.async_block_till_done()
    after = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert {e.entity_id for e in before} == {e.entity_id for e in after}
    assert {e.device_id for e in before} == {e.device_id for e in after}
    assert len(after) == 3
    device = dr.async_get(hass).async_get(after[0].device_id)
    assert device.name == "Mast Flag Status - Kansas"
    assert entry.runtime_data.state_code == "KS"
    assert await hass.config_entries.async_unload(entry.entry_id)
