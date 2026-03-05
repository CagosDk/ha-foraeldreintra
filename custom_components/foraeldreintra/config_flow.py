from __future__ import annotations

import re
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import ForaldreIntraClient, ForaldreIntraAuthError, ForaldreIntraError
from .const import (
    DOMAIN,
    CONF_SCHOOL_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    OPT_SELECTED_CHILDREN,
    OPT_INCLUDE_HISTORY,
    OPT_SCAN_MODE,
    OPT_SCAN_INTERVAL_MINUTES,
    OPT_SCAN_TIMES,
    DEFAULT_INCLUDE_HISTORY,
    DEFAULT_SCAN_MODE,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_TIMES,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCHOOL_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict) -> dict:
    session = async_get_clientsession(hass)
    client = ForaldreIntraClient(
        session=session,
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        school_url=data[CONF_SCHOOL_URL],
    )

    await client.login()
    children = await client.get_children()
    if not children:
        raise ForaldreIntraError("Ingen børn fundet efter login")

    return {"title": "ForældreIntra"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_SCHOOL_URL]}::{user_input[CONF_USERNAME]}".lower()
            )
            self._abort_if_unique_id_configured()

            try:
                info = await _validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except ForaldreIntraAuthError:
                errors["base"] = "auth"
            except ForaldreIntraError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry
        self._children: list[str] = []

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        # Hent børneliste så vi kan vise checkbox multi-select
        try:
            self._children = await self._fetch_children_names()
        except Exception:  # noqa: BLE001
            self._children = []
        # Hvis der ikke allerede er gemt valgte børn, så sæt default til alle nu
        if OPT_SELECTED_CHILDREN not in existing and self._children:
            selected_default = self._children

        existing = self.entry.options

        # Default: alle børn valgt (også hvis der ikke står noget eller står tom liste)
        default_children = self._children
        selected_default = existing.get(OPT_SELECTED_CHILDREN)
        if selected_default is None or selected_default == []:
            selected_default = default_children

        include_history_default = existing.get(OPT_INCLUDE_HISTORY, DEFAULT_INCLUDE_HISTORY)

        scan_mode_default = existing.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)
        scan_interval_default = int(existing.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES))
        scan_times_default = existing.get(OPT_SCAN_TIMES, DEFAULT_SCAN_TIMES)

        if user_input is not None:
            scan_mode = user_input.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)

            # --- Validation afhængigt af scan_mode ---
            if scan_mode == "interval":
                minutes = int(user_input.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES))
                if minutes < 1 or minutes > 1440:
                    errors[OPT_SCAN_INTERVAL_MINUTES] = "invalid_range"

            if scan_mode == "fixed_times":
                csv = (user_input.get(OPT_SCAN_TIMES) or "").strip()
                if not csv:
                    errors[OPT_SCAN_TIMES] = "required"
                elif not self._validate_times_csv(csv):
                    errors[OPT_SCAN_TIMES] = "invalid_time"

            if not errors:
                # --- POLISH: ryd irrelevante felter før vi gemmer ---
                cleaned = dict(user_input)

                if scan_mode == "interval":
                    # ignorér scan_times helt
                    cleaned[OPT_SCAN_TIMES] = ""
                    # sørg for at interval altid er et tal
                    cleaned[OPT_SCAN_INTERVAL_MINUTES] = int(
                        cleaned.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES)
                    )
                else:  # fixed_times
                    # ignorér interval (vi gemmer et fornuftigt tal, men coordinator ignorerer det)
                    cleaned[OPT_SCAN_INTERVAL_MINUTES] = DEFAULT_SCAN_INTERVAL_MINUTES
                    cleaned[OPT_SCAN_TIMES] = (cleaned.get(OPT_SCAN_TIMES) or "").strip()

                return self.async_create_entry(title="", data=cleaned)

        # Checkbox multi-select (LIST)
        children_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=self._children,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        )

        # Pæn dropdown for scan_mode
        scan_mode_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value="interval", label="Interval"),
                    selector.SelectOptionDict(value="fixed_times", label="Faste tidspunkter"),
                ],
                multiple=False,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

        schema = vol.Schema(
            {
                vol.Required(OPT_SELECTED_CHILDREN, default=selected_default): children_selector,
                vol.Required(OPT_INCLUDE_HISTORY, default=include_history_default): bool,
                vol.Required(OPT_SCAN_MODE, default=scan_mode_default): scan_mode_selector,
                # Optional: ellers blokerer UI "Send" når det ikke er relevant
                vol.Optional(OPT_SCAN_INTERVAL_MINUTES, default=scan_interval_default): vol.Coerce(int),
                vol.Optional(OPT_SCAN_TIMES, default=scan_times_default): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def _fetch_children_names(self) -> list[str]:
        session = async_get_clientsession(self.hass)
        client = ForaldreIntraClient(
            session=session,
            username=self.entry.data[CONF_USERNAME],
            password=self.entry.data[CONF_PASSWORD],
            school_url=self.entry.data[CONF_SCHOOL_URL],
        )
        await client.login()
        children = await client.get_children()
        return sorted({c.name for c in children if c.name})

    def _validate_times_csv(self, csv: str) -> bool:
        parts = [p.strip() for p in csv.split(",") if p.strip()]
        if not parts:
            return False
        for p in parts:
            if not re.match(r"^\d{2}:\d{2}$", p):
                return False
            hh, mm = p.split(":")
            h = int(hh)
            m = int(mm)
            if h < 0 or h > 23 or m < 0 or m > 59:
                return False
        return True
