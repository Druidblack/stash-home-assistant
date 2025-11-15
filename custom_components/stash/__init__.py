from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, CONF_URL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Stash integration (YAML not supported)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Stash from a config entry."""
    session = async_get_clientsession(hass)
    graphql_url: str = entry.data[CONF_URL].rstrip("/")

    client = StashClient(graphql_url, session)
    coordinator = StashDataUpdateCoordinator(hass, client)

    # Первое обновление — чтобы сразу были данные в сенсорах
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        domain_data.pop(entry.entry_id, None)
        if not domain_data:
            hass.data.pop(DOMAIN, None)
    return unload_ok


class StashError(Exception):
    """Base error for Stash API."""


class StashClient:
    """Simple async GraphQL client for Stash (no authentication)."""

    def __init__(self, graphql_url: str, session) -> None:
        # graphql_url should point directly to /graphql
        self._url = graphql_url
        self._session = session

    async def _post(self, query: str) -> dict[str, Any]:
        """Send GraphQL query and raise on error."""
        payload = {"query": query}
        async with async_timeout.timeout(10):
            async with self._session.post(self._url, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise StashError(f"HTTP {resp.status} from Stash: {text}")
                data = await resp.json()

        if "errors" in data:
            raise StashError(f"GraphQL errors: {data['errors']}")
        return data

    async def _post_allow_errors(self, query: str) -> dict[str, Any]:
        """Send GraphQL query and return JSON even if it contains errors."""
        payload = {"query": query}
        async with async_timeout.timeout(10):
            async with self._session.post(self._url, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise StashError(f"HTTP {resp.status} from Stash: {text}")
                return await resp.json()

    async def async_get_scenes_count(self) -> int:
        data = await self._post("query { findScenes { count } }")
        return int(data["data"]["findScenes"]["count"])

    async def async_get_movies_count(self) -> int:
        """Return number of movies/groups (supporting old/new schemas)."""
        # Newer Stash versions: Groups
        data = await self._post_allow_errors("query { findGroups { count } }")
        if "data" in data and data["data"] and data["data"].get("findGroups"):
            try:
                return int(data["data"]["findGroups"]["count"])
            except (KeyError, TypeError, ValueError):
                pass

        # Older versions: Movies
        data = await self._post_allow_errors("query { findMovies { count } }")
        if "errors" in data or "data" not in data:
            raise StashError(
                f"GraphQL error getting movies/groups: {data.get('errors')}"
            )

        try:
            return int(data["data"]["findMovies"]["count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise StashError(
                f"Unexpected response for movies/groups count: {data}"
            ) from exc

    async def async_get_performers_count(self) -> int:
        data = await self._post("query { findPerformers { count } }")
        return int(data["data"]["findPerformers"]["count"])

    async def async_get_studios_count(self) -> int:
        data = await self._post("query { findStudios { count } }")
        return int(data["data"]["findStudios"]["count"])

    async def async_get_tags_count(self) -> int:
        data = await self._post("query { findTags { count } }")
        return int(data["data"]["findTags"]["count"])

    async def async_get_images_count(self) -> int:
        data = await self._post("query { findImages { count } }")
        return int(data["data"]["findImages"]["count"])

    async def async_get_galleries_count(self) -> int:
        data = await self._post("query { findGalleries { count } }")
        return int(data["data"]["findGalleries"]["count"])

    async def async_get_markers_count(self) -> int:
        data = await self._post("query { findSceneMarkers { count } }")
        return int(data["data"]["findSceneMarkers"]["count"])

    async def async_get_version(self) -> str | None:
        """Return Stash version string (e.g. 'v0.28.1')."""
        data = await self._post("query { version { version } }")
        try:
            return str(data["data"]["version"]["version"])
        except (KeyError, TypeError, ValueError):
            return None

    async def async_metadata_scan(self) -> None:
        """Trigger library scan."""
        await self._post("mutation { metadataScan(input:{}) }")

    async def async_metadata_clean(self) -> None:
        """Run metadataClean (Tools -> Clean)."""
        query = 'mutation { metadataClean(input: {dryRun: false, paths: ""}) }'
        await self._post(query)

    async def async_metadata_generate(self) -> None:
        """Run metadataGenerate using default task settings."""
        # Используются настройки задачи Generate из UI Stash
        await self._post("mutation { metadataGenerate(input: {}) }")

    async def async_metadata_auto_tag(self) -> None:
        """Run metadataAutoTag using default task settings."""
        # Используются настройки задачи Auto Tag из UI Stash
        await self._post("mutation { metadataAutoTag(input: {}) }")
        
    async def async_metadata_identify(self) -> None:
        """Запустить Identify с использованием указанных stash-box endpoints.

        Сейчас по умолчанию используем только StashDB.
        При желании можно дописать сюда и другие публичные/частные endpoints.
        """
        endpoints: list[str] = [
            "https://stashdb.org/graphql",
            # сюда можно добавить другие, если нужно:
            # "https://fansdb.cc/graphql",
            # "https://theporndb.net/graphql",
            # "https://pmvstash.org/graphql",
        ]

        sources_str = ",\n                ".join(
            f'{{ source: {{ stash_box_endpoint: "{ep}" }} }}'
            for ep in endpoints
        )

        query = f"""
        mutation {{
          metadataIdentify(
            input: {{
              sources: [
                {sources_str}
              ]
            }}
          )
        }}
        """
        await self._post(query)






class StashDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that periodically fetches data from Stash."""

    def __init__(self, hass: HomeAssistant, client: StashClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Stash",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Stash."""
        try:
            scenes = await self.client.async_get_scenes_count()
            movies = await self.client.async_get_movies_count()
            performers = await self.client.async_get_performers_count()
            studios = await self.client.async_get_studios_count()
            tags = await self.client.async_get_tags_count()
            images = await self.client.async_get_images_count()
            galleries = await self.client.async_get_galleries_count()
            markers = await self.client.async_get_markers_count()
            version = await self.client.async_get_version()

            return {
                "scenes": scenes,
                "movies": movies,
                "performers": performers,
                "studios": studios,
                "tags": tags,
                "images": images,
                "galleries": galleries,
                "markers": markers,
                "version": version,
            }
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error communicating with Stash: {err}") from err
