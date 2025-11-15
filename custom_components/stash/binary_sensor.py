from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from . import StashDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Stash binary sensors."""
    data: dict[str, Any] = hass.data[DOMAIN][entry.entry_id]
    coordinator: StashDataUpdateCoordinator = data["coordinator"]

    async_add_entities([StashOnlineBinarySensor(coordinator, entry)])


class StashOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor showing whether Stash GraphQL is reachable."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StashDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_online"
        self._attr_name = "Online"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Stash",
            manufacturer="Stash",
        )

    @property
    def is_on(self) -> bool:
        """Return True if last coordinator update succeeded."""
        # Если последнее обновление провалилось — HA поставит last_update_success = False
        return bool(self.coordinator.last_update_success)
