from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import DOMAIN, PLATFORMS, OPT_SELECTED_CHILDREN
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
        """Fjern entities fra entity registry som ikke længere er valgt."""
        reg = er.async_get(hass)

        selected_names = set(updated_entry.options.get(OPT_SELECTED_CHILDREN, []))
        selected_slugs = {slugify(n) for n in selected_names}

        prefixes = [
            f"{entry.entry_id}_homework_",
            f"{entry.entry_id}_weekplan_",
            f"{entry.entry_id}_weekplan_general_",
            f"{entry.entry_id}_weekplan_focus_",
            f"{entry.entry_id}_weekplan_schedule_",
        ]
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

            for prefix in prefixes:
                if entity.unique_id.startswith(prefix):
                    child_slug = entity.unique_id.replace(prefix, "", 1)
                    break

            if child_slug is None:
                continue

            if not selected_slugs:
                continue

            if child_slug not in selected_slugs:
                reg.async_remove(entity.entity_id)

    async def _options_updated(_: HomeAssistant, updated_entry: ConfigEntry) -> None:
        """Når options ændres: auto-remove + refresh nu + reload."""
        if updated_entry.entry_id != entry.entry_id:
            return

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
