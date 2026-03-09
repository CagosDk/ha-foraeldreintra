from __future__ import annotations

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
    DEFAULT_DISPLAY_PERIOD,
    DEFAULT_INCLUDE_WEEKPLAN_FOCUS,
    DEFAULT_INCLUDE_WEEKPLAN_GENERAL,
    DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE,
    DEFAULT_SHOW_HOMEWORK_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_FOCUS_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_SENSORS,
    DEFAULT_SUBJECT_ALIASES,
    DOMAIN,
    OPT_ADD_HOMEWORK_MARKDOWN,
    OPT_ADD_WEEKPLAN_MARKDOWN,
    OPT_DISPLAY_PERIOD,
    OPT_INCLUDE_WEEKPLAN_FOCUS,
    OPT_INCLUDE_WEEKPLAN_GENERAL,
    OPT_INCLUDE_WEEKPLAN_SCHEDULE,
    OPT_SELECTED_CHILDREN,
    OPT_SHOW_HOMEWORK_SENSORS,
    OPT_SHOW_WEEKPLAN_FOCUS_SENSORS,
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
        try:
            self._children = await self._fetch_children_names()
        except Exception:
            self._children = []

        existing = self.entry.options

        selected_default = existing.get(OPT_SELECTED_CHILDREN)
        if (selected_default is None or selected_default == []) and self._children:
            selected_default = list(self._children)

        if user_input is not None:
            cleaned = dict(user_input)

            if not cleaned.get(OPT_SELECTED_CHILDREN) and self._children:
                cleaned[OPT_SELECTED_CHILDREN] = list(self._children)

            cleaned[OPT_SHOW_HOMEWORK_SENSORS] = bool(
                cleaned.get(OPT_SHOW_HOMEWORK_SENSORS, DEFAULT_SHOW_HOMEWORK_SENSORS)
            )
            cleaned[OPT_ADD_HOMEWORK_MARKDOWN] = bool(
                cleaned.get(OPT_ADD_HOMEWORK_MARKDOWN, DEFAULT_ADD_HOMEWORK_MARKDOWN)
            )

            cleaned[OPT_SHOW_WEEKPLAN_SENSORS] = bool(
                cleaned.get(OPT_SHOW_WEEKPLAN_SENSORS, DEFAULT_SHOW_WEEKPLAN_SENSORS)
            )
            cleaned[OPT_SHOW_WEEKPLAN_GENERAL_SENSORS] = bool(
                cleaned.get(
                    OPT_SHOW_WEEKPLAN_GENERAL_SENSORS,
                    DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS,
                )
            )
            cleaned[OPT_SHOW_WEEKPLAN_FOCUS_SENSORS] = bool(
                cleaned.get(
                    OPT_SHOW_WEEKPLAN_FOCUS_SENSORS,
                    DEFAULT_SHOW_WEEKPLAN_FOCUS_SENSORS,
                )
            )
            cleaned[OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS] = bool(
                cleaned.get(
                    OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
                    DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
                )
            )

            cleaned[OPT_INCLUDE_WEEKPLAN_GENERAL] = bool(
                cleaned.get(
                    OPT_INCLUDE_WEEKPLAN_GENERAL,
                    DEFAULT_INCLUDE_WEEKPLAN_GENERAL,
                )
            )
            cleaned[OPT_INCLUDE_WEEKPLAN_FOCUS] = bool(
                cleaned.get(
                    OPT_INCLUDE_WEEKPLAN_FOCUS,
                    DEFAULT_INCLUDE_WEEKPLAN_FOCUS,
                )
            )
            cleaned[OPT_INCLUDE_WEEKPLAN_SCHEDULE] = bool(
                cleaned.get(
                    OPT_INCLUDE_WEEKPLAN_SCHEDULE,
                    DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE,
                )
            )

            cleaned[OPT_ADD_WEEKPLAN_MARKDOWN] = bool(
                cleaned.get(
                    OPT_ADD_WEEKPLAN_MARKDOWN,
                    DEFAULT_ADD_WEEKPLAN_MARKDOWN,
                )
            )

            cleaned[OPT_SUBJECT_ALIASES] = str(
                cleaned.get(OPT_SUBJECT_ALIASES, DEFAULT_SUBJECT_ALIASES) or ""
            ).strip()

            return self.async_create_entry(title="", data=cleaned)

        schema_dict: dict = {}

        if self._children:
            schema_dict[
                vol.Required(
                    OPT_SELECTED_CHILDREN,
                    default=selected_default,
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._children,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )

        schema_dict[
            vol.Required(
                OPT_DISPLAY_PERIOD,
                default=existing.get(OPT_DISPLAY_PERIOD, DEFAULT_DISPLAY_PERIOD),
            )
        ] = selector.SelectSelector(
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
            vol.Required(
                OPT_SHOW_HOMEWORK_SENSORS,
                default=existing.get(OPT_SHOW_HOMEWORK_SENSORS, DEFAULT_SHOW_HOMEWORK_SENSORS),
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_ADD_HOMEWORK_MARKDOWN,
                default=existing.get(OPT_ADD_HOMEWORK_MARKDOWN, DEFAULT_ADD_HOMEWORK_MARKDOWN),
            )
        ] = bool

        schema_dict[
            vol.Required(
                OPT_INCLUDE_WEEKPLAN_GENERAL,
                default=existing.get(OPT_INCLUDE_WEEKPLAN_GENERAL, DEFAULT_INCLUDE_WEEKPLAN_GENERAL),
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_INCLUDE_WEEKPLAN_FOCUS,
                default=existing.get(OPT_INCLUDE_WEEKPLAN_FOCUS, DEFAULT_INCLUDE_WEEKPLAN_FOCUS),
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_INCLUDE_WEEKPLAN_SCHEDULE,
                default=existing.get(OPT_INCLUDE_WEEKPLAN_SCHEDULE, DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE),
            )
        ] = bool

        schema_dict[
            vol.Required(
                OPT_SHOW_WEEKPLAN_SENSORS,
                default=existing.get(OPT_SHOW_WEEKPLAN_SENSORS, DEFAULT_SHOW_WEEKPLAN_SENSORS),
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_SHOW_WEEKPLAN_GENERAL_SENSORS,
                default=existing.get(
                    OPT_SHOW_WEEKPLAN_GENERAL_SENSORS,
                    DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS,
                ),
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_SHOW_WEEKPLAN_FOCUS_SENSORS,
                default=existing.get(
                    OPT_SHOW_WEEKPLAN_FOCUS_SENSORS,
                    DEFAULT_SHOW_WEEKPLAN_FOCUS_SENSORS,
                ),
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
                default=existing.get(
                    OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
                    DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
                ),
            )
        ] = bool
        schema_dict[
            vol.Required(
                OPT_ADD_WEEKPLAN_MARKDOWN,
                default=existing.get(OPT_ADD_WEEKPLAN_MARKDOWN, DEFAULT_ADD_WEEKPLAN_MARKDOWN),
            )
        ] = bool

        schema_dict[
            vol.Optional(
                OPT_SUBJECT_ALIASES,
                default=str(existing.get(OPT_SUBJECT_ALIASES, DEFAULT_SUBJECT_ALIASES) or ""),
            )
        ] = str

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors={},
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
