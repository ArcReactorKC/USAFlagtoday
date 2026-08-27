"""Normalized flag status and human-readable reason."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MastConfigEntry
from .entity import MastEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: MastConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the two status sensors."""
    async_add_entities([MastStatusSensor(entry), MastReasonSensor(entry)])


class MastStatusSensor(MastEntity, SensorEntity):
    """Machine-readable flag status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["full_staff", "half_staff"]

    def __init__(self, entry: MastConfigEntry) -> None:
        super().__init__(entry, "flag_status")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.status


class MastReasonSensor(MastEntity, SensorEntity):
    """Mast's title; the full text remains available in the reason attribute."""

    def __init__(self, entry: MastConfigEntry) -> None:
        super().__init__(entry, "flag_status_reason")

    @property
    def native_value(self) -> str | None:
        reason = self.coordinator.data.reason
        # Home Assistant entity states must not exceed 255 characters.
        return reason[:255] if reason else None
