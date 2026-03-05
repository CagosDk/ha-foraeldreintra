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

        # Hent børn – men lad aldrig flowet crashe hvis det fejler
        try:
            self._children = await self._fetch_children_names()
        except Exception:  # noqa: BLE001
            self._children = []

        existing = self.entry.options

        include_history_default = existing.get(OPT_INCLUDE_HISTORY, DEFAULT_INCLUDE_HISTORY)
        scan_mode_default = existing.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)
        scan_interval_default = int(existing.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES))
        scan_times_default = existing.get(OPT_SCAN_TIMES, DEFAULT_SCAN_TIMES)

        # Default: alle børn valgt (hvis vi kender dem)
        selected_default = existing.get(OPT_SELECTED_CHILDREN)
        if (selected_default is None or selected_default == []) and self._children:
            selected_default = list(self._children)

        if user_input is not None:
            scan_mode = user_input.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)

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
                cleaned = dict(user_input)

                # Hvis brugeren ender med tom liste, så vælg alle (hvis vi kender dem)
                if not cleaned.get(OPT_SELECTED_CHILDREN) and self._children:
                    cleaned[OPT_SELECTED_CHILDREN] = list(self._children)

                # Polish: ryd irrelevante felter før vi gemmer
                if scan_mode == "interval":
                    cleaned[OPT_SCAN_TIMES] = ""
                    cleaned[OPT_SCAN_INTERVAL_MINUTES] = int(
                        cleaned.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES)
                    )
                else:
                    cleaned[OPT_SCAN_INTERVAL_MINUTES] = DEFAULT_SCAN_INTERVAL_MINUTES
                    cleaned[OPT_SCAN_TIMES] = (cleaned.get(OPT_SCAN_TIMES) or "").strip()

                return self.async_create_entry(title="", data=cleaned)

        schema_dict = {}

        # Børn (checkbox multi-select) – kun hvis vi faktisk har børn
        if self._children:
            children_selector = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._children,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
            schema_dict[vol.Required(OPT_SELECTED_CHILDREN, default=selected_default)] = children_selector

        schema_dict[vol.Required(OPT_INCLUDE_HISTORY, default=include_history_default)] = bool

        scan_mode_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": "interval", "label": "Interval"},
                    {"value": "fixed_times", "label": "Faste tidspunkter"},
                ],
                multiple=False,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        schema_dict[vol.Required(OPT_SCAN_MODE, default=scan_mode_default)] = scan_mode_selector

        # Optional ellers bliver "Send" blokeret
        schema_dict[vol.Optional(OPT_SCAN_INTERVAL_MINUTES, default=scan_interval_default)] = vol.Coerce(int)
        schema_dict[vol.Optional(OPT_SCAN_TIMES, default=scan_times_default)] = str

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_dict), errors=errors)

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
