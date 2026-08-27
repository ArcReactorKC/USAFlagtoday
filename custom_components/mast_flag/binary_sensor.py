"""Binary flag half-staff status."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MastConfigEntry
from .entity import MastEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: MastConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the half-staff indicator."""
    async_add_entities([MastHalfStaffSensor(entry)])


class MastHalfStaffSensor(MastEntity, BinarySensorEntity):
    """On when Mast reports half-staff; no unrelated device class."""

    def __init__(self, entry: MastConfigEntry) -> None:
        super().__init__(entry, "flag_half_staff")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.is_half_staff
