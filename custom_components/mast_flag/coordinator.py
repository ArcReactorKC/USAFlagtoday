"""One poll per configured location, shared by all entities."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MastAuthError, MastClient, MastError, MastStatus
from .const import CONF_STATE, NAME, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


def configured_state(entry: ConfigEntry) -> str:
    """Return the state selected in options, falling back to initial setup."""
    return entry.options.get(CONF_STATE, entry.data[CONF_STATE])


class MastCoordinator(DataUpdateCoordinator[MastStatus]):
    """Fetch and normalize Mast status."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=NAME,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.state_code = configured_state(entry)
        self.client = MastClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])

    async def _async_update_data(self) -> MastStatus:
        try:
            return await self.client.async_get_status(self.state_code)
        except MastAuthError:
            raise ConfigEntryAuthFailed("Mast rejected the API key") from None
        except MastError as err:
            raise UpdateFailed(str(err)) from None
