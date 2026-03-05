from __future__ import annotations

from datetime import date, datetime, timedelta
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
    OPT_DAYS_BACK,
    OPT_DAYS_FORWARD,
    OPT_HIDE_EMPTY_CHILDREN,
    OPT_SORT_MODE,
    OPT_MAX_ITEMS,
    OPT_IGNORE_UNKNOWN_SUBJECT,
    DEFAULT_INCLUDE_HISTORY,
    DEFAULT_DAYS_BACK,
    DEFAULT_DAYS_FORWARD,
    DEFAULT_HIDE_EMPTY_CHILDREN,
    DEFAULT_SORT_MODE,
    DEFAULT_MAX_ITEMS,
    DEFAULT_IGNORE_UNKNOWN_SUBJECT,
)
from .coordinator import ForaldreIntraCoordinator


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:  # noqa: BLE001
        return None


def _get_options(entry: ConfigEntry) -> dict[str, Any]:
    return {
        "selected_children": entry.options.get(OPT_SELECTED_CHILDREN, []),
        "include_history": entry.options.get(OPT_INCLUDE_HISTORY, DEFAULT_INCLUDE_HISTORY),
        "days_back": int(entry.options.get(OPT_DAYS_BACK, DEFAULT_DAYS_BACK)),
        "days_forward": int(entry.options.get(OPT_DAYS_FORWARD, DEFAULT_DAYS_FORWARD)),
        "hide_empty_children": entry.options.get(OPT_HIDE_EMPTY_CHILDREN, DEFAULT_HIDE_EMPTY_CHILDREN),
        "sort_mode": entry.options.get(OPT_SORT_MODE, DEFAULT_SORT_MODE),
        "max_items": int(entry.options.get(OPT_MAX_ITEMS, DEFAULT_MAX_ITEMS)),
        "ignore_unknown_subject": entry.options.get(OPT_IGNORE_UNKNOWN_SUBJECT, DEFAULT_IGNORE_UNKNOWN_SUBJECT),
    }


def _filter_items(items: list[dict[str, Any]], opts: dict[str, Any], child: str | None = None) -> list[dict[str, Any]]:
    today = date.today()
    include_history = bool(opts["include_history"])
    days_back = max(0, int(opts["days_back"]))
    days_forward = max(0, int(opts["days_forward"]))
    max_items = max(1, int(opts["max_items"]))
    ignore_unknown = bool(opts["ignore_unknown_subject"])

    start = today - timedelta(days=days_back) if include_history else today
    end = today + timedelta(days=days_forward)

    selected_children: list[str] = opts["selected_children"] or []
    selected_set = set(selected_children)

    out: list[dict[str, Any]] = []
    for it in items:
        barn = (it.get("barn") or "").strip()
        fag = (it.get("fag") or "").strip()

        if selected_children and barn not in selected_set:
            continue

        if child is not None and barn != child:
            continue

        if ignore_unknown and fag.lower() == "ukendt":
            continue

        d = _parse_iso_date(it.get("dato"))
        if d is None:
            # hvis dato ikke kan parses, behold (så vi ikke mister data)
            out.append(it)
            continue

        if d < start or d > end:
            continue

        out.append(it)

    sort_mode = opts["sort_mode"]
    if sort_mode == "child_then_date":
        out.sort(key=lambda x: ((x.get("barn") or ""), (x.get("dato") or ""), (x.get("fag") or "")))
    else:
        out.sort(key=lambda x: ((x.get("dato") or ""), (x.get("barn") or ""), (x.get("fag") or "")))

    return out[:max_items]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ForaldreIntraCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    children = [c.get("name") for c in data.get("children", []) if c.get("name")]
    all_items = data.get("items", [])

    opts = _get_options(entry)
    selected_children = opts["selected_children"] or []
    selected_set = set(selected_children)

    # "Alle" sensor altid
    entities: list[SensorEntity] = [ForaeldreIntraAllHomeworkSensor(coordinator, entry)]

    # Child sensors
    hide_empty = bool(opts["hide_empty_children"])

    for child_name in children:
        if selected_children and child_name not in selected_set:
            continue

        child_items = _filter_items(all_items, opts, child=child_name)
        if hide_empty and len(child_items) == 0:
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
        opts = _get_options(self._entry)
        filtered = _filter_items(items, opts, child=None)
        return len(filtered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = (self.coordinator.data or {}).get("items", [])
        opts = _get_options(self._entry)
        filtered = _filter_items(items, opts, child=None)
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
        opts = _get_options(self._entry)
        filtered = _filter_items(items, opts, child=self._child)
        return len(filtered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = (self.coordinator.data or {}).get("items", [])
        opts = _get_options(self._entry)
        filtered = _filter_items(items, opts, child=self._child)
        return {"items": filtered}
