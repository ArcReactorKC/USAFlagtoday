"""Mast Flag Status integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MastCoordinator

type MastConfigEntry = ConfigEntry[MastCoordinator]

PLATFORMS = (Platform.BINARY_SENSOR, Platform.SENSOR)


async def async_setup_entry(hass: HomeAssistant, entry: MastConfigEntry) -> bool:
    """Set up Mast from a UI config entry."""
    coordinator = MastCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MastConfigEntry) -> bool:
    """Unload all Mast platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
