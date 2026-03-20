from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DATA_HOMEWORK_STATUS_STORE, DOMAIN
from .coordinator import ForaldreIntraCoordinator
from .homework_status import HomeworkStatusStore

SERVICE_MARK_HOMEWORK_DONE = "mark_homework_done"
SERVICE_MARK_HOMEWORK_UNDONE = "mark_homework_undone"

ATTR_HOMEWORK_ID = "homework_id"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_HOMEWORK_ID): cv.string,
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


def _get_status_store(hass: HomeAssistant, entry_id: str) -> HomeworkStatusStore | None:
    """Return status store for a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    status_store_map = domain_data.get(DATA_HOMEWORK_STATUS_STORE, {})
    if not isinstance(status_store_map, dict):
        return None

    store = status_store_map.get(entry_id)
    return store if isinstance(store, HomeworkStatusStore) else None


def _get_coordinator(hass: HomeAssistant, entry_id: str) -> ForaldreIntraCoordinator | None:
    """Return coordinator for a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinator = domain_data.get(entry_id)
    return coordinator if isinstance(coordinator, ForaldreIntraCoordinator) else None


def _target_entry_ids(hass: HomeAssistant, config_entry_id: str | None) -> list[str]:
    """Resolve which config entries a service call should affect."""
    if config_entry_id:
        return [config_entry_id]

    entries: list[ConfigEntry] = hass.config_entries.async_entries(DOMAIN)
    return [entry.entry_id for entry in entries]


async def _set_homework_completed(
    hass: HomeAssistant,
    homework_id: str,
    completed: bool,
    config_entry_id: str | None,
) -> None:
    """Set completion state for homework and update listeners."""
    entry_ids = _target_entry_ids(hass, config_entry_id)

    for entry_id in entry_ids:
        status_store = _get_status_store(hass, entry_id)
        if status_store is None:
            continue

        await status_store.async_set_completed(homework_id, completed)

        coordinator = _get_coordinator(hass, entry_id)
        if coordinator is not None:
            coordinator.async_update_listeners()


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    if hass.services.has_service(DOMAIN, SERVICE_MARK_HOMEWORK_DONE):
        return

    async def async_mark_homework_done(call: ServiceCall) -> None:
        """Mark homework as completed."""
        await _set_homework_completed(
            hass=hass,
            homework_id=call.data[ATTR_HOMEWORK_ID],
            completed=True,
            config_entry_id=call.data.get(ATTR_CONFIG_ENTRY_ID),
        )

    async def async_mark_homework_undone(call: ServiceCall) -> None:
        """Mark homework as not completed."""
        await _set_homework_completed(
            hass=hass,
            homework_id=call.data[ATTR_HOMEWORK_ID],
            completed=False,
            config_entry_id=call.data.get(ATTR_CONFIG_ENTRY_ID),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_HOMEWORK_DONE,
        async_mark_homework_done,
        schema=SERVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_HOMEWORK_UNDONE,
        async_mark_homework_undone,
        schema=SERVICE_SCHEMA,
    )


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister integration services."""
    if hass.services.has_service(DOMAIN, SERVICE_MARK_HOMEWORK_DONE):
        hass.services.async_remove(DOMAIN, SERVICE_MARK_HOMEWORK_DONE)

    if hass.services.has_service(DOMAIN, SERVICE_MARK_HOMEWORK_UNDONE):
        hass.services.async_remove(DOMAIN, SERVICE_MARK_HOMEWORK_UNDONE)
