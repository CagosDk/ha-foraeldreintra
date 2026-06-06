from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    DATA_HOMEWORK_STATUS_STORE,
    DEFAULT_ADD_HOMEWORK_MARKDOWN,
    DEFAULT_ADD_WEEKPLAN_MARKDOWN,
    DEFAULT_INCLUDE_WEEKPLAN_FOCUS,
    DEFAULT_INCLUDE_WEEKPLAN_GENERAL,
    DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE,
    DEFAULT_SHOW_HOMEWORK_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_FOCUS_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
    DEFAULT_SHOW_WEEKPLAN_SENSORS,
    DEFAULT_SUBJECT_ALIASES,
    DEFAULT_WEEKPLAN_DERIVED_HOMEWORK_ENABLED,
    DOMAIN,
    OPT_ADD_HOMEWORK_MARKDOWN,
    OPT_ADD_WEEKPLAN_MARKDOWN,
    OPT_INCLUDE_WEEKPLAN_FOCUS,
    OPT_INCLUDE_WEEKPLAN_GENERAL,
    OPT_INCLUDE_WEEKPLAN_SCHEDULE,
    OPT_SELECTED_CHILDREN,
    OPT_SHOW_HOMEWORK_SENSORS,
    OPT_SHOW_WEEKPLAN_FOCUS_SENSORS,
    OPT_SHOW_WEEKPLAN_GENERAL_SENSORS,
    OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
    OPT_SHOW_WEEKPLAN_SENSORS,
    OPT_SUBJECT_ALIASES,
    OPT_WEEKPLAN_DERIVED_HOMEWORK_ENABLED,
    OPT_WEEKPLAN_DERIVED_HOMEWORK_KEYWORDS,
)
from .coordinator import ForaldreIntraCoordinator
from .decoding import _decode_display_value, _decode_homework_item, _decode_weekplan
from .formatting import (
    STANDARD_SUBJECT_ALIASES,
    _build_display_title,
    _build_homework_markdown,
    _build_weekplan_markdown,
    _extract_practice_text_from_general_content,
    _extract_year_from_weekplan,
    _formatted_date_to_iso,
    _lesson_matches_practice_marker,
    _normalize_subject_value,
    _parse_keyword_lines,
    _parse_subject_aliases,
    _plan_focus_only,
    _plan_general_only,
    _plan_schedule_only,
    _week_short,
)
from .homework_ids import build_homework_id
from .homework_status import HomeworkStatusStore


# ---------------------------------------------------------------------------
# ConfigEntry-dependent helpers
# ---------------------------------------------------------------------------

def _filter_items(
    entry: ConfigEntry,
    items: list[dict[str, Any]],
    child: str | None = None,
) -> list[dict[str, Any]]:
    selected_children: list[str] = [
        _decode_display_value(name) for name in entry.options.get(OPT_SELECTED_CHILDREN, [])
    ]
    selected_set = set(selected_children)

    child = _decode_display_value(child) if child is not None else None

    out: list[dict[str, Any]] = []

    for it in items:
        barn = _decode_display_value(it.get("barn") or "").strip()

        if selected_children and barn not in selected_set:
            continue
        if child is not None and barn != child:
            continue

        out.append(it)

    out.sort(key=lambda x: ((x.get("dato") or ""), (x.get("barn") or ""), (x.get("fag") or "")))
    return out


def _weekplan_keywords(entry: ConfigEntry) -> list[str]:
    raw_value = entry.options.get(OPT_WEEKPLAN_DERIVED_HOMEWORK_KEYWORDS)
    user_keywords = _parse_keyword_lines(raw_value)

    seen: set[str] = set()
    result: list[str] = []

    for item in user_keywords:
        normalized = item.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


def _derive_homework_from_weekplans(
    entry: ConfigEntry,
    weeklyplans: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enabled = bool(
        entry.options.get(
            OPT_WEEKPLAN_DERIVED_HOMEWORK_ENABLED,
            DEFAULT_WEEKPLAN_DERIVED_HOMEWORK_ENABLED,
        )
    )
    if not enabled:
        return []

    keywords = _weekplan_keywords(entry)
    if not keywords:
        return []

    derived: list[dict[str, Any]] = []

    for child_name_raw, raw_plan in (weeklyplans or {}).items():
        child_name = _decode_display_value(child_name_raw) or ""
        plan = _decode_weekplan(raw_plan or {})
        items = plan.get("items", []) if isinstance(plan.get("items"), list) else []
        days = plan.get("days", []) if isinstance(plan.get("days"), list) else []
        year = _extract_year_from_weekplan(plan)

        for general_item in items:
            if general_item.get("type") != "general":
                continue

            subject = (_decode_display_value(general_item.get("subject")) or "").strip()
            subject_normalized = _normalize_subject_value(subject)
            match = _extract_practice_text_from_general_content(
                general_item.get("content_text") or "",
                keywords,
            )
            if not match:
                continue

            task_title, practice_text = match

            for day in days:
                lesson_plans = day.get("lesson_plans", []) if isinstance(day.get("lesson_plans"), list) else []
                formatted_date = (_decode_display_value(day.get("formatted_date")) or "").strip()
                iso_date = _formatted_date_to_iso(formatted_date, year)

                if not iso_date:
                    continue

                for lesson in lesson_plans:
                    lesson_subject = _normalize_subject_value(lesson.get("subject"))
                    lesson_text = (_decode_display_value(lesson.get("content_text")) or "").strip()

                    if not lesson_text:
                        continue
                    if subject_normalized and lesson_subject and lesson_subject != subject_normalized:
                        continue
                    if not _lesson_matches_practice_marker(lesson_text, task_title, keywords):
                        continue

                    derived.append(
                        {
                            "barn": child_name,
                            "dato": iso_date,
                            "fag": subject or "Ukendt fag",
                            "tekst": f"{task_title}: {practice_text}",
                            "links": [],
                            "source": "weekplan",
                            "derived": True,
                            "title": task_title,
                            "keyword_match": practice_text,
                            "weekplan_day": day.get("day"),
                            "weekplan_date": formatted_date,
                        }
                    )
                    break

    derived = [_decode_homework_item(item) for item in derived]
    derived.sort(
        key=lambda x: ((x.get("dato") or ""), (x.get("barn") or ""), (x.get("fag") or ""))
    )
    return derived


def _merge_homework_items(
    entry: ConfigEntry,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    base_items = [_decode_homework_item(item) for item in list((data or {}).get("items", []) or [])]
    weeklyplans = {
        _decode_display_value(child_name) or "": _decode_weekplan(plan or {})
        for child_name, plan in ((data or {}).get("weeklyplans", {}) or {}).items()
    }
    return base_items + _derive_homework_from_weekplans(entry, weeklyplans)


def _get_status_store(hass: HomeAssistant, entry: ConfigEntry) -> HomeworkStatusStore | None:
    domain_data = hass.data.get(DOMAIN, {})
    status_store_map = domain_data.get(DATA_HOMEWORK_STATUS_STORE, {})
    if not isinstance(status_store_map, dict):
        return None
    store = status_store_map.get(entry.entry_id)
    return store if isinstance(store, HomeworkStatusStore) else None


def _decorate_homework_items(
    hass: HomeAssistant,
    entry: ConfigEntry,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    status_store = _get_status_store(hass, entry)
    decorated: list[dict[str, Any]] = []

    for item in items:
        normalized = _decode_homework_item(dict(item))

        homework_id = build_homework_id(
            child_name=(normalized.get("barn") or ""),
            date_text=(normalized.get("dato") or ""),
            subject=(normalized.get("fag") or ""),
            title=(normalized.get("title") or ""),
            description=(normalized.get("tekst") or ""),
            source=(normalized.get("source") or "homework"),
        )

        normalized["homework_id"] = homework_id
        normalized["completed"] = status_store.is_completed(homework_id) if status_store else False

        decorated.append(normalized)

    return decorated


# ---------------------------------------------------------------------------
# HA entry point
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ForaldreIntraCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    children = [_decode_display_value(c.get("name")) for c in data.get("children", []) if c.get("name")]
    selected_children: list[str] = [
        _decode_display_value(name)
        for name in entry.options.get(OPT_SELECTED_CHILDREN, children)
    ]

    entities: list[SensorEntity] = []

    show_homework = bool(entry.options.get(OPT_SHOW_HOMEWORK_SENSORS, DEFAULT_SHOW_HOMEWORK_SENSORS))
    show_weekplan = bool(entry.options.get(OPT_SHOW_WEEKPLAN_SENSORS, DEFAULT_SHOW_WEEKPLAN_SENSORS))
    show_weekplan_general_sensors = bool(
        entry.options.get(OPT_SHOW_WEEKPLAN_GENERAL_SENSORS, DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS)
    )
    show_weekplan_focus_sensors = bool(
        entry.options.get(OPT_SHOW_WEEKPLAN_FOCUS_SENSORS, DEFAULT_SHOW_WEEKPLAN_FOCUS_SENSORS)
    )
    show_weekplan_schedule_sensors = bool(
        entry.options.get(OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS, DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS)
    )

    if show_homework:
        entities.append(ForaeldreIntraAllHomeworkSensor(hass, coordinator, entry))

    for child_name in children:
        if selected_children and child_name not in set(selected_children):
            continue

        if show_homework:
            entities.append(ForaeldreIntraChildHomeworkSensor(hass, coordinator, entry, child_name))

        if show_weekplan:
            entities.append(ForaeldreIntraChildWeekplanSensor(coordinator, entry, child_name))

        if show_weekplan_general_sensors:
            entities.append(ForaeldreIntraChildWeekplanGeneralSensor(coordinator, entry, child_name))

        if show_weekplan_focus_sensors:
            entities.append(ForaeldreIntraChildWeekplanFocusSensor(coordinator, entry, child_name))

        if show_weekplan_schedule_sensors:
            entities.append(ForaeldreIntraChildWeekplanScheduleSensor(coordinator, entry, child_name))

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Sensor entity classes
# ---------------------------------------------------------------------------

class ForaeldreIntraBaseSensor(CoordinatorEntity[ForaldreIntraCoordinator], SensorEntity):
    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    def _subject_alias_map(self) -> dict[str, str]:
        raw = self._entry.options.get(OPT_SUBJECT_ALIASES, DEFAULT_SUBJECT_ALIASES)
        user_aliases = _parse_subject_aliases(raw)
        merged = dict(STANDARD_SUBJECT_ALIASES)
        merged.update(user_aliases)
        return merged


class ForaeldreIntraAllHomeworkSensor(ForaeldreIntraBaseSensor):
    _attr_name = "ForældreIntra lektier (alle)"
    _attr_icon = "mdi:book-open-page-variant"

    def __init__(self, hass: HomeAssistant, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._hass = hass
        self._attr_unique_id = f"{entry.entry_id}_homework_all"

    @property
    def native_value(self) -> int:
        items = _merge_homework_items(self._entry, self.coordinator.data or {})
        items = _decorate_homework_items(self._hass, self._entry, items)
        return len(_filter_items(self._entry, items, child=None))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = _merge_homework_items(self._entry, self.coordinator.data or {})
        items = _decorate_homework_items(self._hass, self._entry, items)
        filtered = _filter_items(self._entry, items, child=None)

        attrs: dict[str, Any] = {"items": filtered}
        if bool(self._entry.options.get(OPT_ADD_HOMEWORK_MARKDOWN, DEFAULT_ADD_HOMEWORK_MARKDOWN)):
            attrs["markdown"] = _build_homework_markdown(filtered)
        return attrs


class ForaeldreIntraChildHomeworkSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:book-account"

    def __init__(self, hass: HomeAssistant, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._hass = hass
        self._child = _decode_display_value(child_name) or ""
        self._attr_name = f"ForældreIntra lektier ({self._child})"
        self._attr_unique_id = f"{entry.entry_id}_homework_{slugify(self._child)}"

    @property
    def native_value(self) -> int:
        items = _merge_homework_items(self._entry, self.coordinator.data or {})
        items = _decorate_homework_items(self._hass, self._entry, items)
        return len(_filter_items(self._entry, items, child=self._child))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = _merge_homework_items(self._entry, self.coordinator.data or {})
        items = _decorate_homework_items(self._hass, self._entry, items)
        filtered = _filter_items(self._entry, items, child=self._child)

        attrs: dict[str, Any] = {
            "items": filtered,
            "weekplan_derived_homework_enabled": bool(
                self._entry.options.get(
                    OPT_WEEKPLAN_DERIVED_HOMEWORK_ENABLED,
                    DEFAULT_WEEKPLAN_DERIVED_HOMEWORK_ENABLED,
                )
            ),
            "weekplan_derived_homework_keywords": _weekplan_keywords(self._entry),
        }
        if bool(self._entry.options.get(OPT_ADD_HOMEWORK_MARKDOWN, DEFAULT_ADD_HOMEWORK_MARKDOWN)):
            attrs["markdown"] = _build_homework_markdown(filtered)
        return attrs


class ForaeldreIntraChildWeekplanSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:calendar-text"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._child = _decode_display_value(child_name) or ""
        self._attr_name = f"ForældreIntra ugeplan ({self._child})"
        self._attr_unique_id = f"{entry.entry_id}_weekplan_{slugify(self._child)}"

    def _get_plan(self) -> dict[str, Any]:
        weeklyplans = {
            _decode_display_value(name) or "": _decode_weekplan(plan or {})
            for name, plan in ((self.coordinator.data or {}).get("weeklyplans", {}) or {}).items()
        }
        return weeklyplans.get(self._child, {})

    @property
    def native_value(self) -> str:
        return _week_short(self._get_plan().get("week")) or "ingen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        plan = dict(self._get_plan())

        include_general = bool(self._entry.options.get(OPT_INCLUDE_WEEKPLAN_GENERAL, DEFAULT_INCLUDE_WEEKPLAN_GENERAL))
        include_focus = bool(self._entry.options.get(OPT_INCLUDE_WEEKPLAN_FOCUS, DEFAULT_INCLUDE_WEEKPLAN_FOCUS))
        include_schedule = bool(self._entry.options.get(OPT_INCLUDE_WEEKPLAN_SCHEDULE, DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE))
        add_markdown = bool(self._entry.options.get(OPT_ADD_WEEKPLAN_MARKDOWN, DEFAULT_ADD_WEEKPLAN_MARKDOWN))

        items = plan.get("items", [])
        days = plan.get("days", [])

        filtered_days = []
        for day in days:
            new_day = dict(day)
            if not include_focus:
                new_day["lesson_plans"] = []
            if not include_schedule:
                new_day["schedule"] = []

            if new_day.get("lesson_plans") or new_day.get("schedule"):
                filtered_days.append(new_day)

        filtered_items = items if include_general else [x for x in items if x.get("type") != "general"]

        attrs: dict[str, Any] = {
            "barn": self._child,
            "title": _build_display_title(plan),
            "week": _week_short(plan.get("week")),
            "url": plan.get("url"),
            "class_or_group": _decode_display_value(plan.get("class_or_group")) or "",
            "items": filtered_items,
            "days": filtered_days,
        }

        if add_markdown:
            attrs["markdown"] = _build_weekplan_markdown(
                {
                    "title": plan.get("title"),
                    "week": plan.get("week"),
                    "class_or_group": plan.get("class_or_group"),
                    "items": filtered_items,
                    "days": filtered_days,
                },
                include_general=include_general,
                include_focus=include_focus,
                include_schedule=include_schedule,
                alias_map=self._subject_alias_map(),
            )

        return attrs


class ForaeldreIntraChildWeekplanGeneralSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:text-box-outline"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._child = _decode_display_value(child_name) or ""
        self._attr_name = f"ForældreIntra ugeplan generelt ({self._child})"
        self._attr_unique_id = f"{entry.entry_id}_weekplan_general_{slugify(self._child)}"

    def _get_raw_plan(self) -> dict[str, Any]:
        weeklyplans = {
            _decode_display_value(name) or "": _decode_weekplan(plan or {})
            for name, plan in ((self.coordinator.data or {}).get("weeklyplans", {}) or {}).items()
        }
        return dict(weeklyplans.get(self._child, {}) or {})

    @property
    def native_value(self) -> str:
        return _week_short(self._get_raw_plan().get("week")) or "ingen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        raw_plan = self._get_raw_plan()
        plan = _plan_general_only(raw_plan)

        attrs: dict[str, Any] = {
            "barn": self._child,
            "title": _build_display_title(raw_plan),
            "week": _week_short(raw_plan.get("week")),
            "url": plan.get("url"),
            "class_or_group": _decode_display_value(plan.get("class_or_group")) or "",
            "items": plan.get("items", []),
            "days": [],
        }

        if bool(self._entry.options.get(OPT_ADD_WEEKPLAN_MARKDOWN, DEFAULT_ADD_WEEKPLAN_MARKDOWN)):
            attrs["markdown"] = _build_weekplan_markdown(
                {
                    "title": raw_plan.get("title"),
                    "week": raw_plan.get("week"),
                    "class_or_group": raw_plan.get("class_or_group"),
                    "items": plan.get("items", []),
                    "days": [],
                },
                include_general=True,
                include_focus=False,
                include_schedule=False,
                alias_map=self._subject_alias_map(),
            )

        return attrs


class ForaeldreIntraChildWeekplanFocusSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:target-text"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._child = _decode_display_value(child_name) or ""
        self._attr_name = f"ForældreIntra ugeplan fokus ({self._child})"
        self._attr_unique_id = f"{entry.entry_id}_weekplan_focus_{slugify(self._child)}"

    def _get_raw_plan(self) -> dict[str, Any]:
        weeklyplans = {
            _decode_display_value(name) or "": _decode_weekplan(plan or {})
            for name, plan in ((self.coordinator.data or {}).get("weeklyplans", {}) or {}).items()
        }
        return dict(weeklyplans.get(self._child, {}) or {})

    @property
    def native_value(self) -> str:
        return _week_short(self._get_raw_plan().get("week")) or "ingen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        raw_plan = self._get_raw_plan()
        plan = _plan_focus_only(raw_plan)

        attrs: dict[str, Any] = {
            "barn": self._child,
            "title": _build_display_title(raw_plan),
            "week": _week_short(raw_plan.get("week")),
            "url": plan.get("url"),
            "class_or_group": _decode_display_value(plan.get("class_or_group")) or "",
            "items": [],
            "days": plan.get("days", []),
        }

        if bool(self._entry.options.get(OPT_ADD_WEEKPLAN_MARKDOWN, DEFAULT_ADD_WEEKPLAN_MARKDOWN)):
            attrs["markdown"] = _build_weekplan_markdown(
                {
                    "title": raw_plan.get("title"),
                    "week": raw_plan.get("week"),
                    "class_or_group": raw_plan.get("class_or_group"),
                    "items": [],
                    "days": plan.get("days", []),
                },
                include_general=False,
                include_focus=True,
                include_schedule=False,
                alias_map=self._subject_alias_map(),
            )

        return attrs


class ForaeldreIntraChildWeekplanScheduleSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._child = _decode_display_value(child_name) or ""
        self._attr_name = f"ForældreIntra ugeplan skema ({self._child})"
        self._attr_unique_id = f"{entry.entry_id}_weekplan_schedule_{slugify(self._child)}"

    def _get_raw_plan(self) -> dict[str, Any]:
        weeklyplans = {
            _decode_display_value(name) or "": _decode_weekplan(plan or {})
            for name, plan in ((self.coordinator.data or {}).get("weeklyplans", {}) or {}).items()
        }
        return dict(weeklyplans.get(self._child, {}) or {})

    @property
    def native_value(self) -> str:
        return _week_short(self._get_raw_plan().get("week")) or "ingen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        raw_plan = self._get_raw_plan()
        plan = _plan_schedule_only(raw_plan)

        attrs: dict[str, Any] = {
            "barn": self._child,
            "title": _build_display_title(raw_plan),
            "week": _week_short(raw_plan.get("week")),
            "url": plan.get("url"),
            "class_or_group": _decode_display_value(plan.get("class_or_group")) or "",
            "items": [],
            "days": plan.get("days", []),
        }

        if bool(self._entry.options.get(OPT_ADD_WEEKPLAN_MARKDOWN, DEFAULT_ADD_WEEKPLAN_MARKDOWN)):
            attrs["markdown"] = _build_weekplan_markdown(
                {
                    "title": raw_plan.get("title"),
                    "week": raw_plan.get("week"),
                    "class_or_group": raw_plan.get("class_or_group"),
                    "items": [],
                    "days": plan.get("days", []),
                },
                include_general=False,
                include_focus=False,
                include_schedule=True,
                alias_map=self._subject_alias_map(),
            )

        return attrs
