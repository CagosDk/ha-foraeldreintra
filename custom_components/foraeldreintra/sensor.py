from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

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
    ]

    # Opret altid en sensor pr. barn baseret på coordinator.data["children"]
    children = (coordinator.data or {}).get("children", [])
    for child in children:
        name = (child.get("name") or "").strip()
        if name:
            entities.append(ForaeldreIntraChildHomeworkSensor(coordinator, entry, name))

    async_add_entities(entities)


class ForaeldreIntraBaseSensor(CoordinatorEntity[ForaldreIntraCoordinator], SensorEntity):
    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class ForaeldreIntraAllHomeworkSensor(ForaeldreIntraBaseSensor):
    _attr_name = "ForældreIntra lektier (alle)"
    _attr_icon = "mdi:book-open-page-variant"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_homework_all"

    @property
    def native_value(self) -> int:
        items = (self.coordinator.data or {}).get("items", [])
        return len(items)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"items": (self.coordinator.data or {}).get("items", [])}


class ForaeldreIntraChildHomeworkSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:book-account"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._child = child_name
        self._attr_name = f"ForældreIntra lektier ({child_name})"
        self._attr_unique_id = f"{entry.entry_id}_homework_{slugify(child_name)}"

    @property
    def native_value(self) -> int:
        items = (self.coordinator.data or {}).get("items", [])
        return len([i for i in items if (i.get("barn") or "") == self._child])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = (self.coordinator.data or {}).get("items", [])
        child_items = [i for i in items if (i.get("barn") or "") == self._child]
        return {"items": child_items}
