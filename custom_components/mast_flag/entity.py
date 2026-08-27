"""Shared entity identity, attributes, and service device."""

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MastConfigEntry
from .const import DOMAIN, NAME, STATES
from .coordinator import MastCoordinator


class MastEntity(CoordinatorEntity[MastCoordinator]):
    """A read-only entity with identity independent of credentials and location."""

    _attr_has_entity_name = True

    def __init__(self, entry: MastConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{NAME} - {STATES[self.coordinator.state_code]}",
            manufacturer="Mast",
            model="Cloud flag-status service",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.mast.today/api",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose only normalized data, never credentials or raw responses."""
        data = self.coordinator.data
        values = {
            "country_code": data.country_code,
            "state_code": data.state_code,
            "reason": data.reason,
            "authority": data.authority,
            "start": data.start.isoformat() if data.start else None,
            "end": data.end.isoformat() if data.end else None,
            "source_url": data.source_url,
            "cache_is_stale": data.cache_is_stale,
        }
        return {key: value for key, value in values.items() if value is not None}
