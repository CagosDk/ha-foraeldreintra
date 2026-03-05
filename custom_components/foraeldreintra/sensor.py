from __future__ import annotations

from collections import defaultdict
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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

    # Opret barn-sensorer dynamisk (fra første data, hvis muligt)
    # Hvis der endnu ikke er data, kommer de ved næste refresh via async_add_entities i update-listener (nedenfor)
    known_children = sorted({(i.get("barn") or "").strip() for i in (coordinator.data or []) if (i.get("barn") or "").strip()})
    for child_name in known_children:
        entities.append(ForaeldreIntraChildHomeworkSensor(coordinator, entry, child_name))

    async_add_entities(entities)

    # Hvis børn først dukker op senere, tilføj dem ved næste refresh
    coordinator.async_add_listener(lambda: _ensure_child_sensors(hass, entry, async_add_entities))


def _ensure_child_sensors(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: ForaldreIntraCoordinator = hass.data[DOMAIN][entry.entry_id]
    existing_unique_ids = {
        ent.unique_id
        for ent in hass.data.get("sensor", {}).get(DOMAIN, [])  # kan være tomt afhængigt af HA version
        if hasattr(ent, "unique_id")
    }

    children = sorted({(i.get("barn") or "").strip() for i in (coordinator.data or []) if (i.get("barn") or "").strip()})
    new_entities: list[SensorEntity] = []

    for child in children:
        unique = f"{entry.entry_id}_homework_{child.lower()}"
        if unique in existing_unique_ids:
            continue
        new_entities.append(ForaeldreIntraChildHomeworkSensor(coordinator, entry, child))

    if new_entities:
        async_add_entities(new_entities)


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
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"items": self.coordinator.data or []}


class ForaeldreIntraHomeworkByChildSensor(ForaeldreIntraBaseSensor):
    _attr_name = "ForældreIntra lektier (pr. barn)"
    _attr_icon = "mdi:account-child"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_homework_by_child"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in self.coordinator.data or []:
            barn = item.get("barn") or "Ukendt"
            grouped[barn].append(item)
        return {"børn": dict(grouped)}


class ForaeldreIntraChildHomeworkSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:book-account"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._child = child_name
        self._attr_name = f"ForældreIntra lektier ({child_name})"
        self._attr_unique_id = f"{entry.entry_id}_homework_{child_name.lower()}"

    @property
    def native_value(self) -> int:
        return len([i for i in (self.coordinator.data or []) if (i.get("barn") or "") == self._child])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = [i for i in (self.coordinator.data or []) if (i.get("barn") or "") == self._child]
        return {"items": items}
