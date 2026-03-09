from __future__ import annotations

import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ForaldreIntraAuthError, ForaldreIntraClient, ForaldreIntraError
from .const import (
    CONF_PASSWORD,
    CONF_SCHOOL_URL,
    CONF_USERNAME,
    DEFAULT_ADD_HOMEWORK_MARKDOWN,
    DEFAULT_ADD_WEEKPLAN_MARKDOWN,
    DEFAULT_AUTO_REMOVE_UNSELECTED,
    DEFAULT_DISPLAY_PERIOD,
    DEFAULT_INCLUDE_WEEKPLAN_GENERAL,
    DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_MODE,
    DEFAULT_SCAN_TIMES,
    DEFAULT_SHOW_HOMEWORK_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_SENSORS,
    DEFAULT_SUBJECT_ALIASES,
    DOMAIN,
    OPT_ADD_HOMEWORK_MARKDOWN,
    OPT_ADD_WEEKPLAN_MARKDOWN,
    OPT_AUTO_REMOVE_UNSELECTED,
    OPT_DISPLAY_PERIOD,
    OPT_INCLUDE_WEEKPLAN_GENERAL,
    OPT_INCLUDE_WEEKPLAN_SCHEDULE,
    OPT_SCAN_INTERVAL_MINUTES,
    OPT_SCAN_MODE,
    OPT_SCAN_TIMES,
    OPT_SELECTED_CHILDREN,
    OPT_SHOW_HOMEWORK_SENSORS,
    OPT_SHOW_WEEKPLAN_GENERAL_SENSORS,
    OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
    OPT_SHOW_WEEKPLAN_SENSORS,
    OPT_SUBJECT_ALIASES,
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
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry
        self._children: list[str] = []

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        try:
            self._children = await self._fetch_children_names()
        except Exception:
            self._children = []

        existing = self.entry.options

        selected_default = existing.get(OPT_SELECTED_CHILDREN)
        if (selected_default is None or selected_default == []) and self._children:
            selected_default = list(self._children)

        display_default = existing.get(OPT_DISPLAY_PERIOD, DEFAULT_DISPLAY_PERIOD)

        show_homework_default = bool(
            existing.get(OPT_SHOW_HOMEWORK_SENSORS, DEFAULT_SHOW_HOMEWORK_SENSORS)
        )
        add_homework_markdown_default = bool(
            existing.get(OPT_ADD_HOMEWORK_MARKDOWN, DEFAULT_ADD_HOMEWORK_MARKDOWN)
        )

        show_weekplan_default = bool(
            existing.get(OPT_SHOW_WEEKPLAN_SENSORS, DEFAULT_SHOW_WEEKPLAN_SENSORS)
        )
        show_weekplan_general_sensors_default = bool(
            existing.get(
                OPT_SHOW_WEEKPLAN_GENERAL_SENSORS,
                DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS,
            )
        )
        show_weekplan_schedule_sensors_default = bool(
            existing.get(
                OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
                DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
            )
        )
        add_weekplan_markdown_default = bool(
            existing.get(OPT_ADD_WEEKPLAN_MARKDOWN, DEFAULT_ADD_WEEKPLAN_MARKDOWN)
        )
        include_weekplan_schedule_default = bool(
            existing.get(
                OPT_INCLUDE_WEEKPLAN_SCHEDULE,
                DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE,
            )
        )
        include_weekplan_general_default = bool(
            existing.get(
                OPT_INCLUDE_WEEKPLAN_GENERAL,
                DEFAULT_INCLUDE_WEEKPLAN_GENERAL,
            )
        )

        subject_aliases_default = str(
            existing.get(OPT_SUBJECT_ALIASES, DEFAULT_SUBJECT_ALIASES) or ""
        )

        auto_remove_default = bool(
            existing.get(OPT_AUTO_REMOVE_UNSELECTED, DEFAULT_AUTO_REMOVE_UNSELECTED)
        )

        scan_mode_default = existing.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)
        scan_interval_default = int(
            existing.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES)
        )
        scan_times_default = existing.get(OPT_SCAN_TIMES, DEFAULT_SCAN_TIMES)

        if user_input is not None:
            scan_mode = user_input.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)

            if scan_mode == "interval":
                minutes = int(
                    user_input.get(
                        OPT_SCAN_INTERVAL_MINUTES,
                        DEFAULT_SCAN_INTERVAL_MINUTES,
                    )
                )
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

                if not cleaned.get(OPT_SELECTED_CHILDREN) and self._children:
                    cleaned[OPT_SELECTED_CHILDREN] = list(self._children)

                cleaned[OPT_SHOW_HOMEWORK_SENSORS] = bool(
                    cleaned.get(
                        OPT_SHOW_HOMEWORK_SENSORS,
                        DEFAULT_SHOW_HOMEWORK_SENSORS,
                    )
                )
                cleaned[OPT_ADD_HOMEWORK_MARKDOWN] = bool(
                    cleaned.get(
                        OPT_ADD_HOMEWORK_MARKDOWN,
                        DEFAULT_ADD_HOMEWORK_MARKDOWN,
                    )
                )

                cleaned[OPT_SHOW_WEEKPLAN_SENSORS] = bool(
                    cleaned.get(
                        OPT_SHOW_WEEKPLAN_SENSORS,
                        DEFAULT_SHOW_WEEKPLAN_SENSORS,
                    )
                )
                cleaned[OPT_SHOW_WEEKPLAN_GENERAL_SENSORS] = bool(
                    cleaned.get(
                        OPT_SHOW_WEEKPLAN_GENERAL_SENSORS,
                        DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS,
                    )
                )
                cleaned[OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS] = bool(
                    cleaned.get(
                        OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
                        DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
                    )
                )
                cleaned[OPT_ADD_WEEKPLAN_MARKDOWN] = bool(
                    cleaned.get(
                        OPT_ADD_WEEKPLAN_MARKDOWN,
                        DEFAULT_ADD_WEEKPLAN_MARKDOWN,
                    )
                )
                cleaned[OPT_INCLUDE_WEEKPLAN_SCHEDULE] = bool(
                    cleaned.get(
                        OPT_INCLUDE_WEEKPLAN_SCHEDULE,
                        DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE,
                    )
                )
                cleaned[OPT_INCLUDE_WEEKPLAN_GENERAL] = bool(
                    cleaned.get(
                        OPT_INCLUDE_WEEKPLAN_GENERAL,
                        DEFAULT_INCLUDE_WEEKPLAN_GENERAL,
                    )
                )
                cleaned[OPT_SUBJECT_ALIASES] = str(
                    cleaned.get(OPT_SUBJECT_ALIASES, "") or ""
                ).strip()

                cleaned[OPT_AUTO_REMOVE_UNSELECTED] = bool(
                    cleaned.get(
                        OPT_AUTO_REMOVE_UNSELECTED,
                        DEFAULT_AUTO_REMOVE_UNSELECTED,
                    )
                )

                if scan_mode == "interval":
                    cleaned[OPT_SCAN_TIMES] = ""
                    cleaned[OPT_SCAN_INTERVAL_MINUTES] = int(
                        cleaned.get(
                            OPT_SCAN_INTERVAL_MINUTES,
                            DEFAULT_SCAN_INTERVAL_MINUTES,
                        )
                    )
                else:
                    cleaned[OPT_SCAN_INTERVAL_MINUTES] = DEFAULT_SCAN_INTERVAL_MINUTES
                    cleaned[OPT_SCAN_TIMES] = (
                        cleaned.get(OPT_SCAN_TIMES) or ""
                    ).strip()

                return self.async_create_entry(title="", data=cleaned)

        schema_dict: dict = {}

        if self._children:
            children_selector = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._children,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
            schema_dict[
                vol.Required(
                    OPT_SELECTED_CHILDREN,
                    default=selected_default,
                )
            ] = children_selector

        display_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": "all", "label": "Historik + i dag + frem"},
                    {"value": "today_and_future", "label": "Kun i dag + frem"},
                    {"value": "future_only", "label": "Kun frem (fra i morgen)"},
                ],
                multiple=False,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        schema_dict[
            vol.Required(OPT_DISPLAY_PERIOD, default=display_default)
        ] = display_selector

        schema_dict[
            vol.Required(
                OPT_SHOW_HOMEWORK_SENSORS,
                default=show_homework_default,
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_ADD_HOMEWORK_MARKDOWN,
                default=add_homework_markdown_default,
            )
        ] = bool

        schema_dict[
            vol.Required(
                OPT_SHOW_WEEKPLAN_SENSORS,
                default=show_weekplan_default,
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_SHOW_WEEKPLAN_GENERAL_SENSORS,
                default=show_weekplan_general_sensors_default,
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
                default=show_weekplan_schedule_sensors_default,
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_ADD_WEEKPLAN_MARKDOWN,
                default=add_weekplan_markdown_default,
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_INCLUDE_WEEKPLAN_SCHEDULE,
                default=include_weekplan_schedule_default,
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_INCLUDE_WEEKPLAN_GENERAL,
                default=include_weekplan_general_default,
            )
        ] = bool
        schema_dict[
            vol.Optional(
                OPT_SUBJECT_ALIASES,
                default=subject_aliases_default,
            )
        ] = str

        schema_dict[
            vol.Required(
                OPT_AUTO_REMOVE_UNSELECTED,
                default=auto_remove_default,
            )
        ] = bool

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
        schema_dict[
            vol.Required(OPT_SCAN_MODE, default=scan_mode_default)
        ] = scan_mode_selector
        schema_dict[
            vol.Optional(
                OPT_SCAN_INTERVAL_MINUTES,
                default=scan_interval_default,
            )
        ] = vol.Coerce(int)
        schema_dict[
            vol.Optional(OPT_SCAN_TIMES, default=scan_times_default)
        ] = str

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

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
