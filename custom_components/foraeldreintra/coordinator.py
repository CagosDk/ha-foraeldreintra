from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ForaldreIntraClient, ForaldreIntraAuthError, ForaldreIntraError
from .const import (
    CONF_PASSWORD,
    CONF_SCHOOL_URL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ForaldreIntraCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self.client = ForaldreIntraClient(
            session=self.session,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            school_url=entry.data[CONF_SCHOOL_URL],
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )

    async def async_update_options(self, new_entry: ConfigEntry) -> None:
        self.entry = new_entry
        self.async_request_refresh()

    async def _async_update_data(self) -> dict:
        try:
            return await self._fetch_children_and_homework()
        except (ForaldreIntraAuthError, ForaldreIntraError) as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Ukendt fejl: {err}") from err

    async def _fetch_children_and_homework(self) -> dict:
        children = await self.client.get_children()

        if not children:
            await self.client.login()
            children = await self.client.get_children()

        items = await self.client.get_homework_for_children(children)
        weeklyplans = await self.client.get_weekplans_for_children(children)

        return {
            "children": [{"id": c.id, "name": c.name} for c in children],
            "items": items,
            "weeklyplans": weeklyplans,
        }

    async def async_shutdown(self) -> None:
        return None
