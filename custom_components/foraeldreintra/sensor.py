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
    OPT_DISPLAY_PERIOD,
    OPT_ADD_MARKDOWN,
    DEFAULT_DISPLAY_PERIOD,
    DEFAULT_ADD_MARKDOWN,
)
from .coordinator import ForaldreIntraCoordinator


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:  # noqa: BLE001
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
        # period == "all": ingen filter

        out.append(it)

    out.sort(key=lambda x: ((x.get("dato") or ""), (x.get("barn") or ""), (x.get("fag") or "")))
    return out


def _md_escape(text: str) -> str:
    # Minimal escaping til markdown (så det ikke ødelægger kortet)
    return (text or "").replace("\r", "").strip()


def _items_to_markdown(title: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return f"### {title}\nIngen lektier i perioden."

    lines: list[str] = [f"### {title}"]
    current_date = None

    for it in items:
        d = it.get("dato") or ""
        fag = it.get("fag") or ""
        tekst = _md_escape(it.get("tekst") or "")
        links = it.get("links") or []

        if d != current_date:
            current_date = d
            lines.append(f"\n**{d}**")

        head = f"- **{fag}**" if fag else "- **Ukendt**"
        lines.append(head)

        if tekst:
            # indryk tekst under bullet
            for tline in tekst.splitlines():
                tline = tline.strip()
                if tline:
                    lines.append(f"  - {tline}")

        # Links
        for l in links:
            txt = _md_escape(l.get("tekst") or "link")
            url = (l.get("url") or "").strip()
            if url:
                lines.append(f"  - [{txt}]({url})")

    return "\n".join(lines).strip()


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

    @property
    def _add_markdown(self) -> bool:
        return bool(self._entry.options.get(OPT_ADD_MARKDOWN, DEFAULT_ADD_MARKDOWN))


class ForaeldreIntraAllHomeworkSensor(ForaeldreIntraBaseSensor):
    _attr_name = "ForældreIntra lektier (alle)"
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
            attrs["markdown"] = _items_to_markdown("Lektier (alle)", filtered)
        return attrs


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
        filtered = _filter_items(self._entry, items, child=self._child)
        return len(filtered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = (self.coordinator.data or {}).get("items", [])
        filtered = _filter_items(self._entry, items, child=self._child)

        attrs: dict[str, Any] = {"items": filtered}
        if self._add_markdown:
            attrs["markdown"] = _items_to_markdown(f"Lektier ({self._child})", filtered)
        return attrs
