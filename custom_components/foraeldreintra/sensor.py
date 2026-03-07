from __future__ import annotations

import re
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
    OPT_DISPLAY_PERIOD,
    OPT_ADD_MARKDOWN,
    OPT_SHOW_ALL_SENSOR,
    DEFAULT_DISPLAY_PERIOD,
    DEFAULT_ADD_MARKDOWN,
    DEFAULT_SHOW_ALL_SENSOR,
)
from .coordinator import ForaldreIntraCoordinator

DK_WEEKDAY = ["Søndag", "Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag"]
DK_MONTH = [
    "januar",
    "februar",
    "marts",
    "april",
    "maj",
    "juni",
    "juli",
    "august",
    "september",
    "oktober",
    "november",
    "december",
]


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _filter_items(entry: ConfigEntry, items: list[dict[str, Any]], child: str | None = None) -> list[dict[str, Any]]:
    selected_children: list[str] = entry.options.get(OPT_SELECTED_CHILDREN, [])
    selected_set = set(selected_children)
    period = entry.options.get(OPT_DISPLAY_PERIOD, DEFAULT_DISPLAY_PERIOD)
    today = date.today()

    out: list[dict[str, Any]] = []

    for it in items:
        barn = (it.get("barn") or "").strip()

        if selected_children and barn not in selected_set:
            continue
        if child is not None and barn != child:
            continue

        d = _parse_iso_date(it.get("dato"))
        if period == "today_and_future":
            if d is not None and d < today:
                continue
        elif period == "future_only":
            if d is not None and d <= today:
                continue

        out.append(it)

    out.sort(key=lambda x: ((x.get("dato") or ""), (x.get("barn") or ""), (x.get("fag") or "")))
    return out


def _pretty_title_case(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    lower = s.lower()
    return lower[0].upper() + lower[1:]


def _format_header(date_iso: str) -> str:
    d = _parse_iso_date(date_iso)
    if not d:
        return f"# {date_iso}"

    dt = datetime(d.year, d.month, d.day)
    wd = DK_WEEKDAY[(dt.weekday() + 1) % 7]
    return f"# {wd} d.{d.day} {DK_MONTH[d.month - 1]} {d.year}"


def _build_markdown(items: list[dict[str, Any]]) -> str:
    by_date: dict[str, dict[str, dict[str, list[str]]]] = {}

    for it in items:
        dato = (it.get("dato") or "").strip()
        barn = (it.get("barn") or "").strip() or "Ukendt"
        fag = (it.get("fag") or "").strip()
        tekst = (it.get("tekst") or "").strip()
        links = it.get("links") if isinstance(it.get("links"), list) else []

        if not tekst and not links:
            continue

        if not fag and tekst:
            m = re.match(r"^([A-ZÆØÅ0-9 .\\-]{2,30}):\\s*([\\s\\S]*)$", tekst)
            if m:
                fag = m.group(1).strip()
                tekst = (m.group(2) or "").strip()

        if not fag:
            fag = "Ukendt fag"
        elif fag != "Ukendt fag":
            fag = _pretty_title_case(fag)

        by_date.setdefault(dato, {}).setdefault(barn, {}).setdefault(fag, [])

        block = tekst
        for l in links:
            t = (l.get("tekst") or "link").strip()
            u = (l.get("url") or "").strip()
            if u:
                block += f"\\n- [{t}]({u})"

        by_date[dato][barn][fag].append(block.strip())

    dates = sorted([d for d in by_date.keys() if d])
    out = ""

    for i, d_iso in enumerate(dates):
        if i > 0:
            out += "\\n\\n---\\n"

        out += f"{_format_header(d_iso)}\\n\\n"

        children = sorted(by_date[d_iso].keys())
        for child in children:
            out += f"## {child}\\n"
            subjects = sorted(by_date[d_iso][child].keys())
            for subject in subjects:
                out += f"{subject}:\\n"
                for b in by_date[d_iso][child][subject]:
                    out += f"{b}\\n\\n"
            out += "\\n"

    return out.strip() if out.strip() else "Ingen lektier fundet."


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ForaldreIntraCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}

    coordinator_children = [
        c.get("name")
        for c in data.get("children", [])
        if isinstance(c, dict) and c.get("name")
    ]
    selected_children: list[str] = entry.options.get(OPT_SELECTED_CHILDREN, [])

    child_names = coordinator_children[:]
    for child in selected_children:
        if child and child not in child_names:
            child_names.append(child)

    entities: list[SensorEntity] = []

    if bool(entry.options.get(OPT_SHOW_ALL_SENSOR, DEFAULT_SHOW_ALL_SENSOR)):
        entities.append(ForaeldreIntraAllHomeworkSensor(coordinator, entry))

    for child_name in child_names:
        entities.append(ForaeldreIntraChildHomeworkSensor(coordinator, entry, child_name))
        entities.append(ForaeldreIntraChildWeekplanSensor(coordinator, entry, child_name))

    async_add_entities(entities)


class ForaeldreIntraBaseSensor(CoordinatorEntity[ForaldreIntraCoordinator], SensorEntity):
    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def _add_markdown(self) -> bool:
        return bool(self._entry.options.get(OPT_ADD_MARKDOWN, DEFAULT_ADD_MARKDOWN))


class ForaeldreIntraAllHomeworkSensor(ForaeldreIntraBaseSensor):
    _attr_name = "ForældreIntra lektier (alle) test123" 
    _attr_icon = "mdi:book-open-page-variant"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_homework_all"

    @property
    def native_value(self) -> int:
        items = (self.coordinator.data or {}).get("items", [])
        filtered = _filter_items(self._entry, items, child=None)
        return len(filtered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = (self.coordinator.data or {}).get("items", [])
        filtered = _filter_items(self._entry, items, child=None)

        attrs: dict[str, Any] = {"items": filtered}
        if self._add_markdown:
            attrs["markdown"] = _build_markdown(filtered)
        return attrs


class ForaeldreIntraChildHomeworkSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:book-account"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._child = child_name
        self._attr_name = f"ForældreIntra lektier test123 ({child_name})"
        self._attr_unique_id = f"{entry.entry_id}_homework_{slugify(child_name)}"

    @property
    def native_value(self) -> int:
        items = (self.coordinator.data or {}).get("items", [])
        filtered = _filter_items(self._entry, items, child=self._child)
        return len(filtered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = (self.coordinator.data or {}).get("items", [])
        filtered = _filter_items(self._entry, items, child=self._child)

        attrs: dict[str, Any] = {"items": filtered}
        if self._add_markdown:
            attrs["markdown"] = _build_markdown(filtered)
        return attrs


class ForaeldreIntraChildWeekplanSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:calendar-text"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._child = child_name
        self._attr_name = f"ForældreIntra ugeplan ({child_name})"
        self._attr_unique_id = f"{entry.entry_id}_weekplan_{slugify(child_name)}"

    @property
    def native_value(self) -> str:
        weeklyplans = (self.coordinator.data or {}).get("weeklyplans", {})
        plan = weeklyplans.get(self._child, {})
        return plan.get("week") or "ingen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        weeklyplans = (self.coordinator.data or {}).get("weeklyplans", {})
        plan = weeklyplans.get(self._child, {})

        return {
            "barn": self._child,
            "title": plan.get("title"),
            "week": plan.get("week"),
            "class_or_group": plan.get("class_or_group"),
            "url": plan.get("url"),
            "general": plan.get("general", []),
            "days": plan.get("days", []),
            "markdown": plan.get("markdown", "Ingen ugeplan fundet."),
        }
