from __future__ import annotations

import html
import re
from datetime import date, datetime
from typing import Any

from .decoding import _decode_display_value, _decode_homework_item, _decode_weekplan

DK_WEEKDAY = ["Søndag", "Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag"]
DK_MONTH = [
    "januar", "februar", "marts", "april", "maj", "juni",
    "juli", "august", "september", "oktober", "november", "december",
]
DK_MONTH_SHORT_TO_LONG = {
    "jan": "januar", "feb": "februar", "mar": "marts", "apr": "april",
    "maj": "maj", "jun": "juni", "jul": "juli", "aug": "august",
    "sep": "september", "okt": "oktober", "nov": "november", "dec": "december",
}

SECTION_DIVIDER = "<hr>"

SECONDARY_SUBJECTS = {
    "STØTTE", "PÆD", "CO-TEACHER", "BOOS", "BOOSTER",
    "VIKAR", "HJÆLPELÆRER", "PRAKTIKANT", "EKSTRA",
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


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _extract_year_from_weekplan(plan: dict[str, Any]) -> int | None:
    for candidate in [plan.get("url"), plan.get("week"), plan.get("title")]:
        text = (_decode_display_value(candidate) or "").strip()
        match = re.search(r"(?:/|^)(\d{1,2})-(\d{4})(?:$|[^\d])", text)
        if match:
            return int(match.group(2))

        match = re.search(r"\b(20\d{2})\b", text)
        if match:
            return int(match.group(1))

    return None


def _formatted_date_to_iso(formatted_date: str | None, default_year: int | None) -> str | None:
    text = (_decode_display_value(formatted_date) or "").strip()
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


def _expand_formatted_date(date_text: str) -> str:
    text = (_decode_display_value(date_text) or "").strip()
    if not text:
        return ""

    match = re.match(r"^(\d{1,2})\.\s*([A-Za-zæøåÆØÅ]+)\.?$", text)
    if not match:
        return text

    day = match.group(1)
    month_raw = match.group(2).lower()
    month_long = DK_MONTH_SHORT_TO_LONG.get(month_raw, month_raw)
    return f"{day}. {month_long}"


# ---------------------------------------------------------------------------
# Keyword / subject helpers
# ---------------------------------------------------------------------------

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


def _normalize_subject_value(value: str | None) -> str:
    return re.sub(r"\s+", " ", (_decode_display_value(value) or "").strip()).lower()


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
        value = _decode_display_value(value) or ""

        if key:
            aliases[key] = value

    return aliases


def _apply_subject_alias(label: str, alias_map: dict[str, str]) -> str:
    cleaned = (_decode_display_value(label) or "").strip()
    if not cleaned:
        return ""

    upper = cleaned.upper()
    if upper in alias_map:
        return alias_map[upper].strip()

    return cleaned


def _pretty_title_case(s: str) -> str:
    s = (_decode_display_value(s) or "").strip()
    if not s:
        return s
    lower = s.lower()
    return lower[0].upper() + lower[1:]


# ---------------------------------------------------------------------------
# Derived homework helpers (pure logic, no ConfigEntry)
# ---------------------------------------------------------------------------

def _derive_homework_title_from_prefix(prefix: str) -> str:
    cleaned = re.sub(r"\s+", " ", (_decode_display_value(prefix) or "").strip(" :-"))
    if not cleaned:
        return "Lektie"

    lowered = cleaned.lower()
    if "diktat" in lowered:
        return "Diktatord"
    if "læs" in lowered:
        return "Læsning"

    title = cleaned.rstrip(":")
    return title[:1].upper() + title[1:]


def _extract_practice_text_from_general_content(
    content_text: str,
    keywords: list[str],
) -> tuple[str, str] | None:
    text = _decode_display_value(content_text) or ""

    text = re.sub(r"(?i)</?(div|p|br|li)\b[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace(" ", " ")

    raw_lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in raw_lines if line]
    if not lines:
        return None

    def _looks_like_word_list(value: str) -> bool:
        candidate = re.sub(r"^[\-•·]\s*", "", value).strip()
        if not candidate:
            return False

        if "," not in candidate:
            return False

        parts = [p.strip() for p in candidate.split(",") if p.strip()]
        if len(parts) < 3:
            return False

        return all(re.fullmatch(r"[A-Za-zÆØÅæøåéÉüÜöÖäÄáÁóÓíÍúÚñÑ.''\- ]+", part) for part in parts)

    for idx, line in enumerate(lines):
        if ":" not in line:
            continue

        prefix, suffix = line.split(":", 1)
        prefix_clean = prefix.strip()
        prefix_lower = prefix_clean.lower()
        if not any(keyword in prefix_lower for keyword in keywords):
            continue

        suffix_clean = re.sub(r"\s+", " ", suffix).strip(" :-")
        if _looks_like_word_list(suffix_clean):
            return (_derive_homework_title_from_prefix(prefix_clean), suffix_clean)

        for next_line in lines[idx + 1:]:
            candidate = re.sub(r"\s+", " ", next_line).strip(" :-")
            if not candidate:
                continue
            if _looks_like_word_list(candidate):
                return (_derive_homework_title_from_prefix(prefix_clean), candidate)
            break

    return None


def _lesson_matches_practice_marker(
    lesson_text: str,
    task_title: str,
    keywords: list[str],
) -> bool:
    lesson_lower = (_decode_display_value(lesson_text) or "").strip().lower()
    if not lesson_lower:
        return False

    title_lower = (_decode_display_value(task_title) or "").strip().lower()
    if title_lower and title_lower in lesson_lower:
        return True

    if title_lower == "diktatord" and "diktat" in lesson_lower:
        return True

    for keyword in keywords:
        kw = (keyword or "").strip().lower()
        if kw and kw in lesson_lower:
            return True

    return False


# ---------------------------------------------------------------------------
# Schedule formatting
# ---------------------------------------------------------------------------

def _raw_schedule_key(row: dict[str, Any]) -> str:
    subject_short = (_decode_display_value(row.get("subject_short")) or "").strip()
    subject_full = (_decode_display_value(row.get("subject_full")) or "").strip()
    title_str = (_decode_display_value(row.get("title")) or "").strip()
    return (subject_short or subject_full or title_str).strip()


def _normalize_schedule_label(row: dict[str, Any], alias_map: dict[str, str]) -> str:
    subject_full = (_decode_display_value(row.get("subject_full")) or "").strip()
    subject_short = (_decode_display_value(row.get("subject_short")) or "").strip()
    title_str = (_decode_display_value(row.get("title")) or "").strip()

    label = subject_full or subject_short or title_str
    label = _apply_subject_alias(label, alias_map)
    return label.strip()


def _is_secondary_subject(label: str) -> bool:
    label_upper = (_decode_display_value(label) or "").strip().upper()
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
        time_str = (_decode_display_value(row.get("time")) or "").strip()
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


# ---------------------------------------------------------------------------
# Display title / day header helpers
# ---------------------------------------------------------------------------

def _week_short(week_value: str | None) -> str:
    text = (_decode_display_value(week_value) or "").strip()
    if not text:
        return ""
    match = re.match(r"^(\d{1,2})-\d{4}$", text)
    if match:
        return str(int(match.group(1)))
    return text


def _build_display_title(plan: dict[str, Any]) -> str:
    class_or_group = (_decode_display_value(plan.get("class_or_group")) or "").strip()
    week = _week_short(plan.get("week"))

    if class_or_group and week:
        return f"Ugeplan for {class_or_group} - uge {week}"
    if week:
        return f"Ugeplan - uge {week}"
    return (_decode_display_value(plan.get("title")) or "").strip()


def _format_day_header(day: dict[str, Any]) -> str:
    header = (_decode_display_value(day.get("day")) or "").strip()
    formatted_date = _expand_formatted_date(day.get("formatted_date"))
    if formatted_date:
        header = f"{header} {formatted_date}".strip()
    return header


def _format_header(date_iso: str) -> str:
    d = _parse_iso_date(date_iso)
    if not d:
        return f"# {date_iso}"

    dt = datetime(d.year, d.month, d.day)
    wd = DK_WEEKDAY[(dt.weekday() + 1) % 7]
    return f"# {wd} d.{d.day}. {DK_MONTH[d.month - 1]} {d.year}"


def _looks_like_date_heading(text: str) -> bool:
    s = (_decode_display_value(text) or "").strip()
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
    lines = [(_decode_display_value(line) or "").strip() for line in (text or "").splitlines()]
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


# ---------------------------------------------------------------------------
# Markdown builders
# ---------------------------------------------------------------------------

def _build_homework_markdown(items: list[dict[str, Any]]) -> str:
    by_date: dict[str, dict[str, dict[str, list[str]]]] = {}

    for raw_item in items:
        it = _decode_homework_item(raw_item)
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

        for lnk in links:
            t = (_decode_display_value(lnk.get("tekst")) or "link").strip()
            u = (_decode_display_value(lnk.get("url")) or "").strip()
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
    plan = _decode_weekplan(plan)
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
            subject_raw = (_decode_display_value(item.get("subject")) or "").strip()
            subject = _apply_subject_alias(subject_raw, alias_map)

            if subject and subject.lower() not in {"generelt", "(uden angivelse af fag)"}:
                markdown_parts.append(f"### {subject}")

            content_text = (_decode_display_value(item.get("content_text")) or "").strip()
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
                subject = _apply_subject_alias(
                    (_decode_display_value(lesson.get("subject")) or "Generelt").strip(),
                    alias_map,
                )
                if subject and subject.lower() not in {"generelt", "(uden angivelse af fag)"}:
                    day_parts.append(f"### {subject}")

                if lesson.get("content_text"):
                    day_parts.append(_decode_display_value(lesson["content_text"]) or "")

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


# ---------------------------------------------------------------------------
# Plan slice helpers
# ---------------------------------------------------------------------------

def _plan_general_only(plan: dict[str, Any]) -> dict[str, Any]:
    plan = _decode_weekplan(plan)
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
    plan = _decode_weekplan(plan)
    focus_days = []
    for day in plan.get("days", []) or []:
        lesson_plans = day.get("lesson_plans") or []
        if lesson_plans:
            focus_days.append({**day, "schedule": []})

    return {
        "title": plan.get("title"),
        "week": plan.get("week"),
        "url": plan.get("url"),
        "class_or_group": plan.get("class_or_group"),
        "items": [],
        "days": focus_days,
    }


def _plan_schedule_only(plan: dict[str, Any]) -> dict[str, Any]:
    plan = _decode_weekplan(plan)
    schedule_days = []
    for day in plan.get("days", []) or []:
        schedule = day.get("schedule") or []
        if schedule:
            schedule_days.append({**day, "lesson_plans": []})

    return {
        "title": plan.get("title"),
        "week": plan.get("week"),
        "url": plan.get("url"),
        "class_or_group": plan.get("class_or_group"),
        "items": [],
        "days": schedule_days,
    }
