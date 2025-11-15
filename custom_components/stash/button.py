from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from . import StashClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Stash buttons."""
    data: dict[str, Any] = hass.data[DOMAIN][entry.entry_id]
    client: StashClient = data["client"]

    entities: list[ButtonEntity] = [
        StashScanLibraryButton(client, entry),
        StashCleanLibraryButton(client, entry),
        StashGenerateMetadataButton(client, entry),
        StashAutoTagButton(client, entry),
        StashIdentifyScenesButton(client, entry),
    ]

    async_add_entities(entities)


class _BaseStashButton(ButtonEntity):
    """Base button with shared device info."""

    _attr_has_entity_name = True

    def __init__(self, client: StashClient, entry: ConfigEntry) -> None:
        self._client = client
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Stash",
            manufacturer="Stash",
        )


class StashScanLibraryButton(_BaseStashButton):
    """Button to trigger library scan in Stash."""

    def __init__(self, client: StashClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{entry.entry_id}_scan_library"
        self._attr_name = "Scan Library"
        self._attr_icon = "mdi:database-search"

    async def async_press(self) -> None:
        await self._client.async_metadata_scan()


class StashCleanLibraryButton(_BaseStashButton):
    """Button to trigger metadataClean in Stash (Tools -> Clean)."""

    def __init__(self, client: StashClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{entry.entry_id}_clean_library"
        self._attr_name = "Clean Library"
        self._attr_icon = "mdi:broom"

    async def async_press(self) -> None:
        await self._client.async_metadata_clean()


class StashGenerateMetadataButton(_BaseStashButton):
    """Button to trigger metadataGenerate in Stash."""

    def __init__(self, client: StashClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{entry.entry_id}_generate_metadata"
        self._attr_name = "Generate Metadata"
        self._attr_icon = "mdi:auto-fix"

    async def async_press(self) -> None:
        await self._client.async_metadata_generate()


class StashAutoTagButton(_BaseStashButton):
    """Button to trigger metadataAutoTag in Stash."""

    def __init__(self, client: StashClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{entry.entry_id}_auto_tag"
        self._attr_name = "Auto Tag"
        # такая же иконка, как у Tags Count
        self._attr_icon = "mdi:tag-multiple"

    async def async_press(self) -> None:
        await self._client.async_metadata_auto_tag()


class StashIdentifyScenesButton(_BaseStashButton):
    """Button to trigger metadataIdentify in Stash."""

    def __init__(self, client: StashClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{entry.entry_id}_identify_scenes"
        self._attr_name = "Identify Scenes"
        self._attr_icon = "mdi:magnify-scan"

    async def async_press(self) -> None:
        await self._client.async_metadata_identify()
