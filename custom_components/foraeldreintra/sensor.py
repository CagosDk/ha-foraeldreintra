from __future__ import annotations

from collections import defaultdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .coordinator import ForaldreIntraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ForaldreIntraCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        ForaeldreIntraAllHomeworkSensor(coordinator, entry),
        ForaeldreIntraHomeworkByChildSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class ForaeldreIntraBaseSensor(CoordinatorEntity[ForaldreIntraCoordinator], SensorEntity):
    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class ForaeldreIntraAllHomeworkSensor(ForaeldreIntraBaseSensor):
    """Én sensor der viser samlet antal lektier og har listen som attributes."""

    _attr_name = "ForældreIntra lektier (alle)"
    _attr_icon = "mdi:book-open-page-variant"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_homework_all"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "items": self.coordinator.data or [],
        }


class ForaeldreIntraHomeworkByChildSensor(ForaeldreIntraBaseSensor):
    """Én sensor der grupperer lektier pr. barn i attributes."""

    _attr_name = "ForældreIntra lektier (pr. barn)"
    _attr_icon = "mdi:account-child"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_homework_by_child"

    @property
    def native_value(self) -> int:
        # samlet antal
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in self.coordinator.data or []:
            barn = item.get("barn") or "Ukendt"
            grouped[barn].append(item)

        # gør det til almindelig dict for HA
        return {"børn": dict(grouped)}
