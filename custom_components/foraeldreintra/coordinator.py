from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

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


class ForaldreIntraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self.client = ForaldreIntraClient(
            session=self.session,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            school_url=entry.data[CONF_SCHOOL_URL],
        )
        self._last_good_data: dict[str, Any] | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )

    async def async_update_options(self, new_entry: ConfigEntry) -> None:
        self.entry = new_entry
        self.async_set_updated_data(self.data)
        self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self._fetch_children_homework_and_weekplans_with_retry()

            if self._is_valid_result(data):
                self._last_good_data = data
                return data

            _LOGGER.warning(
                "ForældreIntra returnerede tomt eller ugyldigt datasæt. "
                "Beholder sidste gyldige data."
            )

            if self._last_good_data is not None:
                return self._last_good_data

            raise UpdateFailed("Tomt datasæt modtaget og ingen tidligere data at falde tilbage på.")

        except (ForaldreIntraAuthError, ForaldreIntraError) as err:
            if self._last_good_data is not None:
                _LOGGER.warning(
                    "Fejl ved opdatering af ForældreIntra (%s). "
                    "Beholder sidste gyldige data.",
                    err,
                )
                return self._last_good_data
            raise UpdateFailed(str(err)) from err

        except Exception as err:
            if self._last_good_data is not None:
                _LOGGER.exception(
                    "Ukendt fejl ved opdatering af ForældreIntra. "
                    "Beholder sidste gyldige data."
                )
                return self._last_good_data
            raise UpdateFailed(f"Ukendt fejl: {err}") from err

    async def _fetch_children_homework_and_weekplans_with_retry(self) -> dict[str, Any]:
        # Første forsøg
        data = await self._fetch_children_and_homework()

        if self._is_valid_result(data):
            return data

        _LOGGER.warning(
            "ForældreIntra gav tomt/mistænkeligt resultat. Forsøger ny login og henter igen."
        )

        # Tvungen ny login + nyt forsøg
        await self.client.login()
        data_retry = await self._fetch_children_and_homework()

        return data_retry

    async def _fetch_children_and_homework(self) -> dict[str, Any]:
        children = await self.client.get_children()

        if not children:
            _LOGGER.debug("Ingen børn fundet i første forsøg. Logger ind igen.")
            await self.client.login()
            children = await self.client.get_children()

        items = await self.client.get_homework_for_children(children) if children else []
        weeklyplans = await self.client.get_weekplans_for_children(children) if children else {}

        return {
            "children": [{"id": c.id, "name": c.name} for c in children],
            "items": items,
            "weeklyplans": weeklyplans,
        }

    def _is_valid_result(self, data: dict[str, Any] | None) -> bool:
        if not data or not isinstance(data, dict):
            return False

        children = data.get("children") or []
        weeklyplans = data.get("weeklyplans") or {}
        items = data.get("items") or []

        # Hvis vi slet ikke har børn, er resultatet ikke brugbart
        if not children:
            return False

        # Hvis der er børn men både ugeplaner og lektier er helt tomme,
        # er det ofte tegn på udløbet session / fejlsvar snarere end reel "ingen data".
        if not weeklyplans and not items:
            return False

        return True

    async def async_shutdown(self) -> None:
        return None
