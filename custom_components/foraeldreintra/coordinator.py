from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ForaldreIntraClient, ForaldreIntraAuthError, ForaldreIntraError
from .const import (
    DOMAIN,
    CONF_SCHOOL_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    DEFAULT_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


class ForaldreIntraCoordinator(DataUpdateCoordinator[list[dict]]):
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

    async def _async_update_data(self) -> list[dict]:
        try:
            # Login hver refresh er OK som MVP; senere kan vi optimere/cashe session.
            await self.client.login()
            data = await self.client.get_homework()
            return data

        except ForaldreIntraAuthError as err:
            raise UpdateFailed(f"Auth fejl: {err}") from err

        except ForaldreIntraError as err:
            raise UpdateFailed(f"ForældreIntra fejl: {err}") from err

        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Ukendt fejl: {err}") from err
