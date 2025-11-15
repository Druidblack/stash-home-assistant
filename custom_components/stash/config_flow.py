from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_URL

_LOGGER = logging.getLogger(__name__)


async def _normalize_and_test_url(hass: HomeAssistant, url: str) -> str:
    """Нормализовать введённый адрес и проверить, что это Stash GraphQL.

    Возвращает полный URL до /graphql, если всё ок.
    """
    url = url.strip()
    if not url:
        raise RuntimeError("Empty URL")

    # если пользователь забыл http://
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    url = url.rstrip("/")

    # если пользователь указал только host:port — добавляем /graphql
    if not url.endswith("/graphql"):
        graphql_url = f"{url}/graphql"
    else:
        graphql_url = url

    session = async_get_clientsession(hass)
    payload = {"query": "query { version { version } }"}

    async with session.post(graphql_url, json=payload) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"HTTP {resp.status}: {text}")
        data = await resp.json()

    if "errors" in data or "data" not in data:
        raise RuntimeError(f"GraphQL error: {data.get('errors')}")

    return graphql_url


class StashConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Мастер настройки интеграции Stash."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_url = user_input[CONF_URL]

            try:
                graphql_url = await _normalize_and_test_url(self.hass, raw_url)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Cannot connect to Stash at %s: %s", raw_url, err)
                errors["base"] = "cannot_connect"
            else:
                # ДЕЛАЕМ интеграцию МНОГОЭКЗЕМПЛЯРНОЙ:
                # unique_id = сам URL /graphql.
                # Это позволяет добавлять несколько разных Stash (разные URL),
                # но не даёт создать дубль на один и тот же экземпляр.
                await self.async_set_unique_id(graphql_url)
                self._abort_if_unique_id_configured()

                # Красивый заголовок по host:port
                from urllib.parse import urlparse

                parsed = urlparse(graphql_url)
                host = parsed.hostname or graphql_url
                port = parsed.port
                pretty = f"{host}:{port}" if port else host

                return self.async_create_entry(
                    title=f"Stash {pretty}",
                    data={CONF_URL: graphql_url},
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "example": "192.168.1.50:9999 или http://192.168.1.50:9999",
            },
        )
