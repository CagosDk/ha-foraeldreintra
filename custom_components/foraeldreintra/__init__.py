from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import (
    DEFAULT_AUTO_REMOVE_UNSELECTED,
    DEFAULT_SHOW_HOMEWORK_SENSORS,
    DOMAIN,
    OPT_AUTO_REMOVE_UNSELECTED,
    OPT_SELECTED_CHILDREN,
    OPT_SHOW_HOMEWORK_SENSORS,
    PLATFORMS,
)
from .coordinator import ForaldreIntraCoordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up via YAML (ikke brugt)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up via UI config flow."""
    coordinator = ForaldreIntraCoordinator(hass, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    async def _remove_unselected_entities(updated_entry: ConfigEntry) -> None:
        """Fjern entities fra entity registry (opt-in)."""
        reg = er.async_get(hass)

        show_homework = bool(
            updated_entry.options.get(
                OPT_SHOW_HOMEWORK_SENSORS,
                DEFAULT_SHOW_HOMEWORK_SENSORS,
            )
        )
        if not show_homework:
            unique = f"{entry.entry_id}_homework_all"
            entity_id = reg.async_get_entity_id("sensor", DOMAIN, unique)
            if entity_id:
                reg.async_remove(entity_id)

        selected_names = set(updated_entry.options.get(OPT_SELECTED_CHILDREN, []))
        selected_slugs = {slugify(n) for n in selected_names}

        homework_prefix = f"{entry.entry_id}_homework_"
        weekplan_prefix = f"{entry.entry_id}_weekplan_"
        weekplan_general_prefix = f"{entry.entry_id}_weekplan_general_"
        weekplan_schedule_prefix = f"{entry.entry_id}_weekplan_schedule_"
        all_homework_unique = f"{entry.entry_id}_homework_all"

        for entity in list(reg.entities.values()):
            if entity.domain != "sensor":
                continue
            if entity.platform != DOMAIN:
                continue
            if not entity.unique_id:
                continue

            if entity.unique_id == all_homework_unique:
                continue

            child_slug: str | None = None

            if entity.unique_id.startswith(weekplan_general_prefix):
                child_slug = entity.unique_id.replace(weekplan_general_prefix, "", 1)
            elif entity.unique_id.startswith(weekplan_schedule_prefix):
                child_slug = entity.unique_id.replace(weekplan_schedule_prefix, "", 1)
            elif entity.unique_id.startswith(homework_prefix):
                child_slug = entity.unique_id.replace(homework_prefix, "", 1)
            elif entity.unique_id.startswith(weekplan_prefix):
                child_slug = entity.unique_id.replace(weekplan_prefix, "", 1)
            else:
                continue

            if not selected_slugs:
                continue

            if child_slug not in selected_slugs:
                reg.async_remove(entity.entity_id)

    async def _options_updated(_: HomeAssistant, updated_entry: ConfigEntry) -> None:
        """Når options ændres: auto-remove + refresh nu + reload."""
        if updated_entry.entry_id != entry.entry_id:
            return

        if bool(
            updated_entry.options.get(
                OPT_AUTO_REMOVE_UNSELECTED,
                DEFAULT_AUTO_REMOVE_UNSELECTED,
            )
        ):
            await _remove_unselected_entities(updated_entry)

        if hasattr(coordinator, "async_update_options"):
            await coordinator.async_update_options(updated_entry)

        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_options_updated))

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload."""
    coordinator: ForaldreIntraCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        if coordinator and hasattr(coordinator, "async_shutdown"):
            try:
                await coordinator.async_shutdown()
            except Exception:
                pass

        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
