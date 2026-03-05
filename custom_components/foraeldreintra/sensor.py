from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    OPT_SELECTED_CHILDREN,
    OPT_INCLUDE_HISTORY,
    DEFAULT_INCLUDE_HISTORY,
)
from .coordinator import ForaldreIntraCoordinator


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:  # noqa: BLE001
        return None


def _filtered_items(entry: ConfigEntry, items: list[dict[str, Any]], child: str | None = None) -> list[dict[str, Any]]:
    include_history = bool(entry.options.get(OPT_INCLUDE_HISTORY, DEFAULT_INCLUDE_HISTORY))
    selected_children: list[str] = entry.options.get(OPT_SELECTED_CHILDREN, [])

    today = date.today()

    out: list[dict[str, Any]] = []
    for it in items:
        barn = (it.get("barn") or "").strip()
        if selected_children and barn not in set(selected_children):
            continue
        if child is not None and barn != child:
            continue

        if not include_history:
            d = _parse_iso_date(it.get("dato"))
            if d is not None and d < today:
                continue

        out.append(it)

    out.sort(key=lambda x: ((x.get("dato") or ""), (x.get("barn") or ""), (x.get("fag") or "")))
    return out


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ForaldreIntraCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    children = [c.get("name") for c in data.get("children", []) if c.get("name")]
    selected_children: list[str] = entry.options.get(OPT_SELECTED_CHILDREN, children)

    entities: list[SensorEntity] = [ForaeldreIntraAllHomeworkSensor(coordinator, entry)]

    for child_name in children:
        if selected_children and child_name not in set(selected_children):
            continue
        entities.append(ForaeldreIntraChildHomeworkSensor(coordinator, entry, child_name))

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
        filtered = _filtered_items(self._entry, items, child=None)
        return len(filtered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = (self.coordinator.data or {}).get("items", [])
        filtered = _filtered_items(self._entry, items, child=None)
        return {"items": filtered}


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
        filtered = _filtered_items(self._entry, items, child=self._child)
        return len(filtered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = (self.coordinator.data or {}).get("items", [])
        filtered = _filtered_items(self._entry, items, child=self._child)
        return {"items": filtered}
