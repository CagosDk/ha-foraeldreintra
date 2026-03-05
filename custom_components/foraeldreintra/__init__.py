from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import ForaldreIntraCoordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up via YAML (ikke brugt)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up via UI config flow."""
    coordinator = ForaldreIntraCoordinator(hass, entry)

    # Gem coordinator så sensor.py kan finde den
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Listener: når options ændres, så:
    # 1) opdater schedule + trigger refresh NU
    # 2) reload entry så sensorer matcher valg af børn
    async def _options_updated(_: HomeAssistant, updated_entry: ConfigEntry) -> None:
        if updated_entry.entry_id != entry.entry_id:
            return

        # opdater coordinatorens entry reference + schedule og trigger immediate refresh
        await coordinator.async_update_options(updated_entry)

        # reload så entity-listen (barn-sensorer) følger de nye options
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_options_updated))

    # Første fetch (så du har data med det samme efter opsætning)
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload."""
    coordinator: ForaldreIntraCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # ryd schedule-triggers hvis de findes
        if coordinator and hasattr(coordinator, "async_shutdown"):
            try:
                await coordinator.async_shutdown()
            except Exception:  # noqa: BLE001
                pass

        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
