from __future__ import annotations

from datetime import datetime, timedelta, date
import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ForaldreIntraClient, ForaldreIntraAuthError, ForaldreIntraError
from .const import (
    DOMAIN,
    CONF_SCHOOL_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    # options
    OPT_SCAN_MODE,
    OPT_SCAN_INTERVAL_MINUTES,
    OPT_SCAN_TIMES,
    DEFAULT_SCAN_MODE,
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
    # fjern dubletter og sortér
    times = sorted(set(times))
    return times


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

        self._consecutive_failures = 0
        self._unsubs: list[callable] = []

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )

        # Sæt schedule ud fra options
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
            # Slå coordinatorens interval fra, og planlæg ved specifikke tidspunkter
            self.update_interval = None
            csv = self.entry.options.get(OPT_SCAN_TIMES, DEFAULT_SCAN_TIMES)
            times = _parse_times_csv(csv)
            if not times:
                # fallback: 15 min hvis ingen tider er angivet
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
            # Interval mode
            minutes = int(self.entry.options.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES))
            if minutes < 1 or minutes > 1440:
                minutes = DEFAULT_SCAN_INTERVAL_MINUTES

            self.update_interval = timedelta(minutes=minutes)

            # (valgfrit) ekstra interval-tracker, hvis du vil sikre “tick” selv når HA ændrer update_interval:
            # men DataUpdateCoordinator håndterer det fint.
            # Derfor bruger vi ikke async_track_time_interval her.

    async def _scheduled_refresh(self, now: datetime) -> None:
        # Kald en refresh på de faste tidspunkter
        self.async_request_refresh()

    async def async_update_options(self) -> None:
        """Kaldes når options ændres (fra __init__.py)."""
        self._apply_schedule_from_options()

    async def _async_update_data(self) -> dict:
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
        # 1) Prøv at finde børn uden login (kan være tomt ved kold start)
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
        # reset backoff: vi re-applier schedule (så interval kan gå tilbage hvis vi havde backoff)
        self._apply_schedule_from_options()

    def _on_failure(self) -> None:
        self._consecutive_failures += 1

        # Backoff ved fejl: vi skruer kun ned ved interval-mode (fixed_times er allerede “skånsom”)
        scan_mode = self.entry.options.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)
        if scan_mode == "fixed_times":
            return

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

    async def async_shutdown(self) -> None:
        """Kaldes ved unload i __init__.py."""
        self._clear_schedules()
