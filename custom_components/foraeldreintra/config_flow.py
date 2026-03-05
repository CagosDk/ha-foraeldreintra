from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_SCHOOL_URL, CONF_USERNAME, CONF_PASSWORD

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCHOOL_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Valider login og at vi kan hente børn."""
    # Lazy import: undgår at config flow handleren fejler ved import, hvis requirements mangler.
    try:
        from .api import (
            ForaldreIntraClient,
            ForaldreIntraAuthError,
            ForaldreIntraError,
        )
    except Exception as err:  # noqa: BLE001
        # Giver os en rigtig fejl i loggen i stedet for "Invalid handler specified"
        raise RuntimeError(
            "Kunne ikke importere foraeldreintra api (mangler dependency eller import-fejl)."
        ) from err

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

            except Exception as err:  # noqa: BLE001
                # Import/dep fejl -> giv brugeren en "unknown", men loggen vil vise den rigtige årsag.
                # (Hvis du vil, kan vi senere mappe flere fejltyper til pænere beskeder)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
