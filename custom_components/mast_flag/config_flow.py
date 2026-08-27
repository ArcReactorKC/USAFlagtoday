"""UI setup, reauthentication, and validated location options."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    MastAuthError,
    MastClient,
    MastConnectionError,
    MastLocationError,
    MastResponseError,
)
from .const import CONF_COUNTRY, CONF_STATE, COUNTRY_CODE, DOMAIN, NAME, STATES
from .coordinator import configured_state


def _state_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[{"value": code, "label": name} for code, name in STATES.items()],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _key_selector() -> TextSelector:
    return TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def _validate(hass: HomeAssistant, api_key: str, state: str) -> dict[str, str]:
    """Return translated form errors without logging credentials."""
    try:
        await MastClient(async_get_clientsession(hass), api_key).async_get_status(state)
    except MastAuthError:
        return {"base": "invalid_auth"}
    except MastConnectionError:
        return {"base": "cannot_connect"}
    except MastLocationError:
        return {"base": "invalid_location"}
    except MastResponseError:
        return {"base": "invalid_response"}
    return {}


def _duplicate(hass: HomeAssistant, state: str, exclude: str | None = None) -> bool:
    """One entry per state: the public flag status is independent of API account."""
    return any(
        entry.entry_id != exclude and configured_state(entry) == state
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


class MastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure Mast through Devices & Services."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MastOptionsFlow:
        return MastOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            state = user_input[CONF_STATE]
            if user_input[CONF_COUNTRY] != COUNTRY_CODE:
                errors = {"base": "invalid_location"}
            else:
                errors = await _validate(self.hass, user_input[CONF_API_KEY], state)
            if not errors:
                await self.async_set_unique_id(f"{COUNTRY_CODE}_{state}")
                self._abort_if_unique_id_configured()
                if _duplicate(self.hass, state):
                    return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title=f"{NAME} - {STATES[state]}",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): _key_selector(),
                    vol.Required(CONF_COUNTRY, default=COUNTRY_CODE): SelectSelector(
                        SelectSelectorConfig(
                            options=[{"value": "US", "label": "United States"}],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_STATE): _state_selector(),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _validate(self.hass, user_input[CONF_API_KEY], configured_state(entry))
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): _key_selector()}),
            errors=errors,
        )


class MastOptionsFlow(OptionsFlowWithReload):
    """Change location while retaining the existing entities and credentials."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self.config_entry
        if user_input is not None:
            state = user_input[CONF_STATE]
            errors = await _validate(self.hass, entry.data[CONF_API_KEY], state)
            if not errors and _duplicate(self.hass, state, entry.entry_id):
                errors = {"base": "already_configured"}
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry,
                    title=f"{NAME} - {STATES[state]}",
                    unique_id=f"{COUNTRY_CODE}_{state}",
                )
                return self.async_create_entry(title="", data={CONF_STATE: state})
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATE, default=configured_state(entry)): _state_selector(),
                }
            ),
            errors=errors,
        )
