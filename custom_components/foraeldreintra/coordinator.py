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


class ForaldreIntraCoordinator(DataUpdateCoordinator[dict]):
    """
    coordinator.data format:
      {
        "children": [{"id": "...", "name": "Olivia"}, ...],
        "items": [ ... homework items ... ]
      }
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.session = async_get_clientsession(hass)

        self.client = ForaldreIntraClient(
            session=self.session,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            school_url=entry.data[CONF_SCHOOL_URL],
        )

        self._consecutive_failures = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )

    async def _async_update_data(self) -> dict:
        """
        Skånsom strategi:
        - Prøv at hente børn+lektier uden login.
        - Hvis ingen børn -> login og prøv igen (kun ved behov).
        - Hvis auth fejler undervejs -> re-login og prøv én gang.
        - Backoff ved gentagne fejl.
        """
        try:
            data = await self._fetch_children_and_homework()
            self._on_success()
            return data

        except ForaldreIntraAuthError as err:
            _LOGGER.debug("Auth fejl ved hentning, forsøger re-login: %s", err)
            try:
                await self.client.login()
                data = await self._fetch_children_and_homework(force_login=False)
                self._on_success()
                return data
            except Exception as err2:  # noqa: BLE001
                self._on_failure()
                raise UpdateFailed(f"Auth fejl efter re-login: {err2}") from err2

        except (ForaldreIntraError, Exception) as err:  # noqa: BLE001
            self._on_failure()
            raise UpdateFailed(f"Hentning fejlede: {err}") from err

    async def _fetch_children_and_homework(self, force_login: bool = False) -> dict:
        # 1) Prøv at finde børn (uden login)
        children = await self.client.get_children()

        # 2) Hvis ingen børn -> login og prøv igen (kun ved behov)
        if force_login or not children:
            await self.client.login()
            children = await self.client.get_children()

        # 3) Hent lektier ud fra børnelisten (ingen dobbelt get_children)
        items = await self.client.get_homework_for_children(children)

        return {
            "children": [{"id": c.id, "name": c.name} for c in children],
            "items": items,
        }

    def _on_success(self) -> None:
        self._consecutive_failures = 0
        desired = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)
        if self.update_interval != desired:
            self.update_interval = desired
            _LOGGER.debug("Reset update_interval til %s", self.update_interval)

    def _on_failure(self) -> None:
        self._consecutive_failures += 1

        # Simple backoff: efter 3 fejl -> 30 min, efter 6 fejl -> 60 min
        if self._consecutive_failures >= 6:
            new_interval = timedelta(minutes=60)
        elif self._consecutive_failures >= 3:
            new_interval = timedelta(minutes=30)
        else:
            return

        if self.update_interval != new_interval:
            self.update_interval = new_interval
            _LOGGER.warning(
                "Gentagne fejl (%s). Backoff: update_interval sat til %s",
                self._consecutive_failures,
                self.update_interval,
            )
