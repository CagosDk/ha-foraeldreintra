from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ForaldreIntraClient, ForaldreIntraAuthError, ForaldreIntraError
from .const import (
    DOMAIN,
    CONF_SCHOOL_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    OPT_SCAN_MODE,
    OPT_SCAN_INTERVAL_MINUTES,
    OPT_SCAN_TIMES,
    DEFAULT_SCAN_MODE,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_TIMES,
)

_LOGGER = logging.getLogger(__name__)


def _parse_times_csv(csv: str) -> list[tuple[int, int]]:
    parts = [p.strip() for p in (csv or "").split(",") if p.strip()]
    times: list[tuple[int, int]] = []

    for p in parts:
        if not re.match(r"^\d{2}:\d{2}$", p):
            continue

        hh, mm = p.split(":")
        h = int(hh)
        m = int(mm)
        if 0 <= h <= 23 and 0 <= m <= 59:
            times.append((h, m))

    return sorted(set(times))


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
        self._unsubs: list[callable] = []

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )

        self._apply_schedule_from_options()

    def _clear_schedules(self) -> None:
        for u in self._unsubs:
            try:
                u()
            except Exception:  # noqa: BLE001
                pass
        self._unsubs = []

    def _apply_schedule_from_options(self) -> None:
        self._clear_schedules()

        scan_mode = self.entry.options.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)

        if scan_mode == "fixed_times":
            self.update_interval = None
            csv = self.entry.options.get(OPT_SCAN_TIMES, DEFAULT_SCAN_TIMES)
            times = _parse_times_csv(csv)

            # fallback hvis ingen tider er angivet
            if not times:
                self.update_interval = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)
                return

            for (h, m) in times:
                unsub = async_track_time_change(
                    self.hass,
                    self._scheduled_refresh,
                    hour=h,
                    minute=m,
                    second=0,
                )
                self._unsubs.append(unsub)

        else:
            minutes = int(
                self.entry.options.get(
                    OPT_SCAN_INTERVAL_MINUTES,
                    DEFAULT_SCAN_INTERVAL_MINUTES,
                )
            )
            if minutes < 1 or minutes > 1440:
                minutes = DEFAULT_SCAN_INTERVAL_MINUTES

            self.update_interval = timedelta(minutes=minutes)

    async def _scheduled_refresh(self, now: datetime) -> None:
        self.async_request_refresh()

    async def async_update_options(self, new_entry: ConfigEntry) -> None:
        # Opdater entry reference + schedule, og hent data NU
        self.entry = new_entry
        self._apply_schedule_from_options()
        self.async_request_refresh()

    async def _async_update_data(self) -> dict:
        try:
            return await self._fetch_children_and_homework()
        except (ForaldreIntraAuthError, ForaldreIntraError) as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Ukendt fejl: {err}") from err

    async def _fetch_children_and_homework(self) -> dict:
        # Prøv først uden login (kan være tomt ved kold start)
        children = await self.client.get_children()

        # Hvis ingen børn -> login og prøv igen
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
        self._clear_schedules()
