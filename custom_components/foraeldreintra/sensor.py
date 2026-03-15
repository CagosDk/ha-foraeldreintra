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
    DATA_HOMEWORK_STATUS_STORE,
    DEFAULT_ADD_HOMEWORK_MARKDOWN,
    DEFAULT_ADD_WEEKPLAN_MARKDOWN,
    DEFAULT_DISPLAY_PERIOD,
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
    DEFAULT_WEEKPLAN_DERIVED_HOMEWORK_KEYWORDS,
    DOMAIN,
    OPT_ADD_HOMEWORK_MARKDOWN,
    OPT_ADD_WEEKPLAN_MARKDOWN,
    OPT_DISPLAY_PERIOD,
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
from .homework_ids import build_homework_id
from .homework_status import HomeworkStatusStore

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
DK_MONTH_SHORT_TO_LONG = {
    "jan": "januar",
    "feb": "februar",
    "mar": "marts",
    "apr": "april",
    "maj": "maj",
    "jun": "juni",
    "jul": "juli",
    "aug": "august",
    "sep": "september",
    "okt": "oktober",
    "nov": "november",
    "dec": "december",
}

SECTION_DIVIDER = "<hr>"

SECONDARY_SUBJECTS = {
    "STØTTE",
    "PÆD",
    "CO-TEACHER",
    "BOOS",
    "BOOSTER",
    "VIKAR",
    "HJÆLPELÆRER",
    "PRAKTIKANT",
    "EKSTRA",
}

STANDARD_SUBJECT_ALIASES = {
    "DAN": "Dansk",
    "MAT": "Matematik",
    "ENG": "Engelsk",
    "IDR": "Idræt",
    "BIL": "Billedkunst",
    "MUS": "Musik",
    "SVØM": "Svømning",
    "N/T": "Natur/Teknologi",
    "KRIS": "Kristendomskundskab",
    "KLA": "Klassens tid",
    "BOOS": "Booster",
    "PÆD": "Pædagog",
    "KOR": "Kor",
    "STØTTE": "Støtte",
    "CO-TEACHER": "Co-teacher",
    "MASTER": "Master Class",
}


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _filter_items(
    entry: ConfigEntry,
    items: list[dict[str, Any]],
    child: str | None = None,
) -> list[dict[str, Any]]:
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


def _parse_keyword_lines(raw: str | None) -> list[str]:
    if raw is None:
        return []

    text = str(raw).replace(";", "\n").replace(",", "\n")
    keywords: list[str] = []

    for line in text.splitlines():
        value = line.strip().lower()
        if value:
            keywords.append(value)

    return keywords


def _weekplan_keywords(entry: ConfigEntry) -> list[str]:
    defaults = [k.lower() for k in DEFAULT_WEEKPLAN_DERIVED_HOMEWORK_KEYWORDS]
    extra = _parse_keyword_lines(
        entry.options.get(
            OPT_WEEKPLAN_DERIVED_HOMEWORK_KEYWORDS,
            ", ".join(DEFAULT_WEEKPLAN_DERIVED_HOMEWORK_KEYWORDS),
        )
    )

    merged: list[str] = []
    seen: set[str] = set()
    for item in [*defaults, *extra]:
        normalized = item.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(normalized)
    return merged


def _normalize_subject_value(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _extract_year_from_weekplan(plan: dict[str, Any]) -> int | None:
    for candidate in [plan.get("url"), plan.get("week"), plan.get("title")]:
        text = (candidate or "").strip()
        match = re.search(r"(?:/|^)(\d{1,2})-(\d{4})(?:$|[^\d])", text)
        if match:
            return int(match.group(2))

        match = re.search(r"\b(20\d{2})\b", text)
        if match:
            return int(match.group(1))

    return None


def _formatted_date_to_iso(formatted_date: str | None, default_year: int | None) -> str | None:
    text = (formatted_date or "").strip()
    if not text:
        return None

    match = re.match(r"^(\d{1,2})\.\s*([A-Za-zæøåÆØÅ]+)\.?$", text)
    if not match:
        return None

    if default_year is None:
        default_year = date.today().year

    day = int(match.group(1))
    month_key = match.group(2).lower()
    month_name = DK_MONTH_SHORT_TO_LONG.get(month_key, month_key)

    try:
        month = DK_MONTH.index(month_name) + 1
    except ValueError:
        return None

    try:
        return date(default_year, month, day).isoformat()
    except ValueError:
        return None


def _derive_homework_title_from_prefix(prefix: str) -> str:
    cleaned = re.sub(r"\s+", " ", (prefix or "").strip(" :-"))
    if not cleaned:
        return "Øveopgave"

    lowered = cleaned.lower()
    if "diktat" in lowered:
        return "Diktat"
    if "læs" in lowered:
        return "Læsning"

    title = cleaned.rstrip(":")
    return title[:1].upper() + title[1:]


def _extract_practice_text_from_general_content(
    content_text: str,
    keywords: list[str],
) -> tuple[str, str] | None:
    for raw_line in (content_text or "").splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue

        prefix, suffix = line.split(":", 1)
        prefix_clean = prefix.strip()
        suffix_clean = suffix.strip()
        if not suffix_clean:
            continue

        prefix_lower = prefix_clean.lower()
        if any(keyword in prefix_lower for keyword in keywords):
            return (_derive_homework_title_from_prefix(prefix_clean), suffix_clean)

    return None


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

    for child_name, plan in (weeklyplans or {}).items():
        items = plan.get("items", []) if isinstance(plan.get("items"), list) else []
        days = plan.get("days", []) if isinstance(plan.get("days"), list) else []
        year = _extract_year_from_weekplan(plan)

        for general_item in items:
            if general_item.get("type") != "general":
                continue

            subject = (general_item.get("subject") or "").strip()
            subject_normalized = _normalize_subject_value(subject)
            match = _extract_practice_text_from_general_content(
                general_item.get("content_text") or "",
                keywords,
            )
            if not match:
                continue

            task_title, practice_text = match
            task_title_lower = task_title.lower()

            for day in days:
                lesson_plans = day.get("lesson_plans", []) if isinstance(day.get("lesson_plans"), list) else []
                formatted_date = (day.get("formatted_date") or "").strip()
                iso_date = _formatted_date_to_iso(formatted_date, year)

                if not iso_date:
                    continue

                for lesson in lesson_plans:
                    lesson_subject = _normalize_subject_value(lesson.get("subject"))
                    lesson_text = (lesson.get("content_text") or "").strip()

                    if not lesson_text:
                        continue
                    if subject_normalized and lesson_subject and lesson_subject != subject_normalized:
                        continue
                    if task_title_lower not in lesson_text.lower():
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

    derived.sort(
        key=lambda x: ((x.get("dato") or ""), (x.get("barn") or ""), (x.get("fag") or ""))
    )
    return derived


def _merge_homework_items(
    entry: ConfigEntry,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    base_items = list((data or {}).get("items", []) or [])
    weeklyplans = (data or {}).get("weeklyplans", {}) or {}
    return base_items + _derive_homework_from_weekplans(entry, weeklyplans)


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
    return f"# {wd} d.{d.day}. {DK_MONTH[d.month - 1]} {d.year}"


def _parse_subject_aliases(raw: str | None) -> dict[str, str]:
    aliases: dict[str, str] = {}
    if raw is None:
        return aliases

    text = str(raw).replace(";", "\n").replace(",", "\n")
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().upper()
        value = value.strip()

        if key:
            aliases[key] = value

    return aliases


def _apply_subject_alias(label: str, alias_map: dict[str, str]) -> str:
    cleaned = (label or "").strip()
    if not cleaned:
        return ""

    upper = cleaned.upper()
    if upper in alias_map:
        return alias_map[upper].strip()

    return cleaned


def _raw_schedule_key(row: dict[str, Any]) -> str:
    subject_short = (row.get("subject_short") or "").strip()
    subject_full = (row.get("subject_full") or "").strip()
    title_str = (row.get("title") or "").strip()
    return (subject_short or subject_full or title_str).strip()


def _normalize_schedule_label(row: dict[str, Any], alias_map: dict[str, str]) -> str:
    subject_full = (row.get("subject_full") or "").strip()
    subject_short = (row.get("subject_short") or "").strip()
    title_str = (row.get("title") or "").strip()

    label = subject_full or subject_short or title_str
    label = _apply_subject_alias(label, alias_map)
    return label.strip()


def _is_secondary_subject(label: str) -> bool:
    label_upper = (label or "").strip().upper()
    if not label_upper:
        return True
    return label_upper in SECONDARY_SUBJECTS


def _combine_schedule_rows(
    schedule_rows: list[dict[str, Any]],
    alias_map: dict[str, str],
) -> list[str]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    order: list[str] = []

    for row in schedule_rows:
        time_str = (row.get("time") or "").strip()
        raw_key = _raw_schedule_key(row)
        label = _normalize_schedule_label(row, alias_map)

        if not time_str and not label:
            continue

        if time_str not in grouped:
            grouped[time_str] = []
            order.append(time_str)

        if not label:
            continue

        existing = {(lbl.lower(), raw.lower()) for lbl, raw in grouped[time_str]}
        candidate = (label.lower(), raw_key.lower())
        if candidate not in existing:
            grouped[time_str].append((label, raw_key))

    lines: list[str] = []

    for time_str in order:
        entries = grouped.get(time_str, [])

        if entries:
            entries_sorted = sorted(
                entries,
                key=lambda x: (
                    1 if _is_secondary_subject(x[1]) else 0,
                    x[0].lower(),
                ),
            )
            labels_sorted = [label for label, _raw in entries_sorted]
            joined = " / ".join(labels_sorted)

            if time_str:
                lines.append(f"- {time_str} — {joined}")
            else:
                lines.append(f"- {joined}")
        else:
            if time_str:
                lines.append(f"- {time_str}")

    return lines


def _week_short(week_value: str | None) -> str:
    text = (week_value or "").strip()
    if not text:
        return ""
    match = re.match(r"^(\d{1,2})-\d{4}$", text)
    if match:
        return str(int(match.group(1)))
    return text


def _build_display_title(plan: dict[str, Any]) -> str:
    class_or_group = (plan.get("class_or_group") or "").strip()
    week = _week_short(plan.get("week"))

    if class_or_group and week:
        return f"Ugeplan for {class_or_group} - uge {week}"
    if week:
        return f"Ugeplan - uge {week}"
    return (plan.get("title") or "").strip()


def _expand_formatted_date(date_text: str) -> str:
    text = (date_text or "").strip()
    if not text:
        return ""

    match = re.match(r"^(\d{1,2})\.\s*([A-Za-zæøåÆØÅ]+)\.?$", text)
    if not match:
        return text

    day = match.group(1)
    month_raw = match.group(2).lower()
    month_long = DK_MONTH_SHORT_TO_LONG.get(month_raw, month_raw)
    return f"{day}. {month_long}"


def _format_day_header(day: dict[str, Any]) -> str:
    header = (day.get("day") or "").strip()
    formatted_date = _expand_formatted_date(day.get("formatted_date"))
    if formatted_date:
        header = f"{header} {formatted_date}".strip()
    return header


def _looks_like_date_heading(text: str) -> bool:
    s = (text or "").strip()
    if not s.endswith(":"):
        return False

    if re.match(r"^(Mandag|Tirsdag|Onsdag|Torsdag|Fredag|Lørdag|Søndag)\b", s):
        return True

    if re.match(
        r"^(Mandag|Tirsdag|Onsdag|Torsdag|Fredag|Lørdag|Søndag),\s*.*:$",
        s,
        re.IGNORECASE,
    ):
        return True

    return False


def _format_general_content(text: str) -> str:
    lines = [(line or "").strip() for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""

    formatted: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if _looks_like_date_heading(line) and i + 1 < len(lines):
            formatted.append(f"### {line}\n{lines[i + 1]}")
            i += 2
            continue

        if line.endswith(":") and len(line) > 20:
            formatted.append(f"### {line}")
            i += 1
            continue

        formatted.append(line)
        i += 1

    return "\n\n".join(formatted).strip()


def _build_homework_markdown(items: list[dict[str, Any]]) -> str:
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
            m = re.match(r"^([A-ZÆØÅ0-9 .\-]{2,30}):\s*([\s\S]*)$", tekst)
            if m:
                fag = m.group(1).strip()
                tekst = (m.group(2) or "").strip()

        if not fag:
            fag = "Ukendt fag"
        elif fag != "Ukendt fag":
            fag = _pretty_title_case(fag)

        by_date.setdefault(dato, {}).setdefault(barn, {}).setdefault(fag, [])

        block = tekst
        if it.get("derived"):
            block = f"{block}\n*(Kilde: ugeplan)*" if block else "*(Kilde: ugeplan)*"

        for l in links:
            t = (l.get("tekst") or "link").strip()
            u = (l.get("url") or "").strip()
            if u:
                if block:
                    block += "\n"
                block += f"- [{t}]({u})"

        by_date[dato][barn][fag].append(block.strip())

    dates = sorted([d for d in by_date.keys() if d])
    parts: list[str] = []

    for d_iso in dates:
        day_parts: list[str] = [_format_header(d_iso)]

        children = sorted(by_date[d_iso].keys())
        for child in children:
            child_parts: list[str] = [f"## {child}"]
            subjects = sorted(by_date[d_iso][child].keys())

            for subject in subjects:
                subject_lines: list[str] = [f"**{subject}**  "]

                for b in by_date[d_iso][child][subject]:
                    if b:
                        subject_lines.append(b)

                child_parts.append("\n".join(subject_lines))

            day_parts.append("\n\n".join(child_parts))

        parts.append("\n\n\n".join(day_parts))

    return "\n\n<hr>\n\n".join(parts).strip() if parts else "Ingen lektier fundet."


def _build_weekplan_markdown(
    plan: dict[str, Any],
    include_general: bool,
    include_focus: bool,
    include_schedule: bool,
    alias_map: dict[str, str],
) -> str:
    title = _build_display_title(plan)
    items = plan.get("items") or []
    days = plan.get("days") or []

    markdown_parts: list[str] = []

    if title:
        markdown_parts.append(f"# {title}")

    general_items = [x for x in items if x.get("type") == "general"]

    visible_days = []
    for day in days:
        lesson_plans = day.get("lesson_plans") or []
        schedule = day.get("schedule") or []
        has_focus = include_focus and bool(lesson_plans)
        has_schedule = include_schedule and bool(schedule)
        if has_focus or has_schedule:
            visible_days.append(day)

    has_general_section = include_general and bool(general_items)
    has_day_section = bool(visible_days)

    if has_general_section:
        markdown_parts.append("## Generelt")

        for idx, item in enumerate(general_items):
            subject_raw = (item.get("subject") or "").strip()
            subject = _apply_subject_alias(subject_raw, alias_map)

            if subject and subject.lower() not in {"generelt", "(uden angivelse af fag)"}:
                markdown_parts.append(f"### {subject}")

            content_text = (item.get("content_text") or "").strip()
            if content_text:
                markdown_parts.append(_format_general_content(content_text))

            if idx < len(general_items) - 1:
                markdown_parts.append(SECTION_DIVIDER)

    if has_general_section and has_day_section:
        markdown_parts.append(SECTION_DIVIDER)

    for idx, day in enumerate(visible_days):
        day_parts: list[str] = []

        header = _format_day_header(day)
        if header:
            day_parts.append(f"## {header}")

        lesson_plans = day.get("lesson_plans", [])

        if include_focus:
            for lesson_idx, lesson in enumerate(lesson_plans):
                subject = _apply_subject_alias((lesson.get("subject") or "Generelt").strip(), alias_map)
                if subject and subject.lower() not in {"generelt", "(uden angivelse af fag)"}:
                    day_parts.append(f"### {subject}")

                if lesson.get("content_text"):
                    day_parts.append(lesson["content_text"])

                if lesson_idx < len(lesson_plans) - 1:
                    day_parts.append(SECTION_DIVIDER)

        if include_schedule:
            schedule_lines = _combine_schedule_rows(day.get("schedule", []), alias_map)

            if schedule_lines:
                if include_focus and lesson_plans:
                    day_parts.append(SECTION_DIVIDER)
                day_parts.append("### Skema")
                day_parts.append("\n".join(schedule_lines))

        markdown_parts.append("\n\n".join(day_parts))

        if idx < len(visible_days) - 1:
            markdown_parts.append(SECTION_DIVIDER)

    return "\n\n".join(part for part in markdown_parts if part).strip() or "Ingen ugeplan fundet."


def _plan_general_only(plan: dict[str, Any]) -> dict[str, Any]:
    items = [x for x in (plan.get("items") or []) if x.get("type") == "general"]
    return {
        "title": plan.get("title"),
        "week": plan.get("week"),
        "url": plan.get("url"),
        "class_or_group": plan.get("class_or_group"),
        "items": items,
        "days": [],
    }


def _plan_focus_only(plan: dict[str, Any]) -> dict[str, Any]:
    focus_days = []
    for day in plan.get("days", []) or []:
        lesson_plans = day.get("lesson_plans") or []
        if lesson_plans:
            focus_days.append(
                {
                    **day,
                    "schedule": [],
                }
            )

    return {
        "title": plan.get("title"),
        "week": plan.get("week"),
        "url": plan.get("url"),
        "class_or_group": plan.get("class_or_group"),
        "items": [],
        "days": focus_days,
    }


def _plan_schedule_only(plan: dict[str, Any]) -> dict[str, Any]:
    schedule_days = []
    for day in plan.get("days", []) or []:
        schedule = day.get("schedule") or []
        if schedule:
            schedule_days.append(
                {
                    **day,
                    "lesson_plans": [],
                }
            )

    return {
        "title": plan.get("title"),
        "week": plan.get("week"),
        "url": plan.get("url"),
        "class_or_group": plan.get("class_or_group"),
        "items": [],
        "days": schedule_days,
    }


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
        normalized = dict(item)

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ForaldreIntraCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    children = [c.get("name") for c in data.get("children", []) if c.get("name")]
    selected_children: list[str] = entry.options.get(OPT_SELECTED_CHILDREN, children)

    entities: list[SensorEntity] = []

    show_homework = bool(
        entry.options.get(OPT_SHOW_HOMEWORK_SENSORS, DEFAULT_SHOW_HOMEWORK_SENSORS)
    )
    show_weekplan = bool(
        entry.options.get(OPT_SHOW_WEEKPLAN_SENSORS, DEFAULT_SHOW_WEEKPLAN_SENSORS)
    )
    show_weekplan_general_sensors = bool(
        entry.options.get(
            OPT_SHOW_WEEKPLAN_GENERAL_SENSORS,
            DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS,
        )
    )
    show_weekplan_focus_sensors = bool(
        entry.options.get(
            OPT_SHOW_WEEKPLAN_FOCUS_SENSORS,
            DEFAULT_SHOW_WEEKPLAN_FOCUS_SENSORS,
        )
    )
    show_weekplan_schedule_sensors = bool(
        entry.options.get(
            OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
            DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS,
        )
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
        filtered = _filter_items(self._entry, items, child=None)
        return len(filtered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = _merge_homework_items(self._entry, self.coordinator.data or {})
        items = _decorate_homework_items(self._hass, self._entry, items)
        filtered = _filter_items(self._entry, items, child=None)

        attrs: dict[str, Any] = {"items": filtered}
        if bool(
            self._entry.options.get(
                OPT_ADD_HOMEWORK_MARKDOWN,
                DEFAULT_ADD_HOMEWORK_MARKDOWN,
            )
        ):
            attrs["markdown"] = _build_homework_markdown(filtered)
        return attrs


class ForaeldreIntraChildHomeworkSensor(ForaeldreIntraBaseSensor):
    _attr_icon = "mdi:book-account"

    def __init__(self, hass: HomeAssistant, coordinator: ForaldreIntraCoordinator, entry: ConfigEntry, child_name: str) -> None:
        super().__init__(coordinator, entry)
        self._hass = hass
        self._child = child_name
        self._attr_name = f"ForældreIntra lektier ({child_name})"
        self._attr_unique_id = f"{entry.entry_id}_homework_{slugify(child_name)}"

    @property
    def native_value(self) -> int:
        items = _merge_homework_items(self._entry, self.coordinator.data or {})
        items = _decorate_homework_items(self._hass, self._entry, items)
        filtered = _filter_items(self._entry, items, child=self._child)
        return len(filtered)

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
        if bool(
            self._entry.options.get(
                OPT_ADD_HOMEWORK_MARKDOWN,
                DEFAULT_ADD_HOMEWORK_MARKDOWN,
            )
        ):
            attrs["markdown"] = _build_homework_markdown(filtered)
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
        return _week_short(plan.get("week")) or "ingen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        weeklyplans = (self.coordinator.data or {}).get("weeklyplans", {})
        plan = dict(weeklyplans.get(self._child, {}) or {})

        include_general = bool(
            self._entry.options.get(
                OPT_INCLUDE_WEEKPLAN_GENERAL,
                DEFAULT_INCLUDE_WEEKPLAN_GENERAL,
            )
        )
        include_focus = bool(
            self._entry.options.get(
                OPT_INCLUDE_WEEKPLAN_FOCUS,
                DEFAULT_INCLUDE_WEEKPLAN_FOCUS,
            )
        )
        include_schedule = bool(
            self._entry.options.get(
                OPT_INCLUDE_WEEKPLAN_SCHEDULE,
                DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE,
            )
        )
        add_markdown = bool(
            self._entry.options.get(
                OPT_ADD_WEEKPLAN_MARKDOWN,
                DEFAULT_ADD_WEEKPLAN_MARKDOWN,
            )
        )

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
            "class_or_group": plan.get("class_or_group"),
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
        self._child = child_name
        self._attr_name = f"ForældreIntra ugeplan generelt ({child_name})"
        self._attr_unique_id = f"{entry.entry_id}_weekplan_general_{slugify(child_name)}"

    @property
    def native_value(self) -> str:
        weeklyplans = (self.coordinator.data or {}).get("weeklyplans", {})
        plan = weeklyplans.get(self._child, {})
        return _week_short(plan.get("week")) or "ingen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        weeklyplans = (self.coordinator.data or {}).get("weeklyplans", {})
        raw_plan = dict(weeklyplans.get(self._child, {}) or {})
        plan = _plan_general_only(raw_plan)

        attrs: dict[str, Any] = {
            "barn": self._child,
            "title": _build_display_title(raw_plan),
            "week": _week_short(raw_plan.get("week")),
            "url": plan.get("url"),
            "class_or_group": plan.get("class_or_group"),
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
        self._child = child_name
        self._attr_name = f"ForældreIntra ugeplan fokus ({child_name})"
        self._attr_unique_id = f"{entry.entry_id}_weekplan_focus_{slugify(child_name)}"

    @property
    def native_value(self) -> str:
        weeklyplans = (self.coordinator.data or {}).get("weeklyplans", {})
        plan = weeklyplans.get(self._child, {})
        return _week_short(plan.get("week")) or "ingen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        weeklyplans = (self.coordinator.data or {}).get("weeklyplans", {})
        raw_plan = dict(weeklyplans.get(self._child, {}) or {})
        plan = _plan_focus_only(raw_plan)

        attrs: dict[str, Any] = {
            "barn": self._child,
            "title": _build_display_title(raw_plan),
            "week": _week_short(raw_plan.get("week")),
            "url": plan.get("url"),
            "class_or_group": plan.get("class_or_group"),
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
        self._child = child_name
        self._attr_name = f"ForældreIntra ugeplan skema ({child_name})"
        self._attr_unique_id = f"{entry.entry_id}_weekplan_schedule_{slugify(child_name)}"

    @property
    def native_value(self) -> str:
        weeklyplans = (self.coordinator.data or {}).get("weeklyplans", {})
        plan = weeklyplans.get(self._child, {})
        return _week_short(plan.get("week")) or "ingen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        weeklyplans = (self.coordinator.data or {}).get("weeklyplans", {})
        raw_plan = dict(weeklyplans.get(self._child, {}) or {})
        plan = _plan_schedule_only(raw_plan)

        attrs: dict[str, Any] = {
            "barn": self._child,
            "title": _build_display_title(raw_plan),
            "week": _week_short(raw_plan.get("week")),
            "url": plan.get("url"),
            "class_or_group": plan.get("class_or_group"),
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
