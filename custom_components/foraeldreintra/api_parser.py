from __future__ import annotations

import html
import json
import re
from typing import Any

from bs4 import BeautifulSoup


def _html_to_text(html_fragment: str) -> str:
    if not html_fragment:
        return ""

    soup = BeautifulSoup(html_fragment, "html.parser")

    for br in soup.find_all("br"):
        br.replace_with("\n")

    text = soup.get_text("\n", strip=True)
    lines = [(line or "").replace("\xa0", " ").strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def _clean_child_name(name: str) -> str:
    """Fjern evt. 'item' suffix fra barnets navn i URL."""
    n = (name or "").strip()
    if n.lower().endswith("item"):
        n = n[:-4]
    return n


def _extract_diary_id(html_text: str) -> str | None:
    m = re.search(r"weeklyplansandhomework/diary/(\d+)", html_text)
    if m:
        return m.group(1)

    m = re.search(r"diary/(\d+)(?:/|\"|'|\?)", html_text)
    if m:
        return m.group(1)

    return None


def _extract_latest_weekplan_from_list(html_text: str) -> dict[str, str] | None:
    """Finder første publicerede ugeplan på /weeklyplansandhomework/list."""
    soup = BeautifulSoup(html_text, "html.parser")

    container = soup.select_one("ul.sk-weekly-plans-list-container")
    if not container:
        return None

    first_link = container.select_one(
        "li a[href*='/weeklyplansandhomework/item/class/']"
    )
    if not first_link:
        return None

    href = (first_link.get("href") or "").strip()
    title = first_link.get_text(" ", strip=True)

    match = re.search(r"/item/class/(\d{2}-\d{4})", href)
    if not match:
        return None

    return {
        "weekplan_id": match.group(1),
        "href": href,
        "title": title,
    }


def _parse_weekplan_page(
    html_text: str,
    weekplan_id: str,
    fallback_title: str,
    url: str,
) -> dict[str, Any]:
    """Parser ugeplansside fra WeeklyPlansApp JSON til sensor-format."""
    soup = BeautifulSoup(html_text, "html.parser")
    root = soup.select_one("#root")

    app_data_raw = ""
    if root:
        app_data_raw = root.get("data-clientlogic-settings-weeklyplansapp", "") or root.get(
            "data-clientlogic-settings-WeeklyPlansApp", ""
        )

    if not app_data_raw:
        return {
            "title": fallback_title,
            "week": weekplan_id,
            "url": url,
            "class_or_group": None,
            "items": [],
            "days": [],
        }

    try:
        app_data = json.loads(html.unescape(app_data_raw))
    except Exception:
        return {
            "title": fallback_title,
            "week": weekplan_id,
            "url": url,
            "class_or_group": None,
            "items": [],
            "days": [],
        }

    selected_plan = app_data.get("SelectedPlan") or {}
    general_plan = selected_plan.get("GeneralPlan") or {}
    daily_plans = selected_plan.get("DailyPlans") or []

    formatted_week = (selected_plan.get("FormattedWeek") or weekplan_id or "").strip()
    class_or_group = (selected_plan.get("ClassOrGroup") or "").strip() or None

    title = fallback_title
    if class_or_group and formatted_week:
        title = f"Ugeplan for {class_or_group} - uge {formatted_week}"
    elif formatted_week:
        title = f"Ugeplan - uge {formatted_week}"

    items: list[dict[str, Any]] = []
    days: list[dict[str, Any]] = []

    for lesson_plan in general_plan.get("LessonPlans") or []:
        subject_obj = lesson_plan.get("Subject") or {}
        subject = (
            subject_obj.get("FormattedTitle")
            or subject_obj.get("Title")
            or "Generelt"
        )
        content_html = lesson_plan.get("Content") or ""
        content_text = _html_to_text(content_html)

        if content_text:
            items.append(
                {
                    "type": "general",
                    "subject": subject,
                    "content_text": content_text,
                }
            )

    for daily_plan in daily_plans:
        day_name = (daily_plan.get("Day") or "").strip()
        formatted_date = (daily_plan.get("FormattedDate") or "").strip()

        lesson_plans_out: list[dict[str, Any]] = []
        schedule_out: list[dict[str, str]] = []

        for lesson_plan in daily_plan.get("LessonPlans") or []:
            subject_obj = lesson_plan.get("Subject") or {}
            subject = (
                subject_obj.get("FormattedTitle")
                or subject_obj.get("Title")
                or "Generelt"
            )
            content_html = lesson_plan.get("Content") or ""
            content_text = _html_to_text(content_html)

            if content_text:
                lesson_plans_out.append(
                    {
                        "subject": subject,
                        "content_text": content_text,
                    }
                )

        for row in daily_plan.get("Schedule") or []:
            schedule_out.append(
                {
                    "time": (row.get("TimeString") or "").strip(),
                    "subject_short": (row.get("ShortSubjectTitle") or "").strip(),
                    "subject_full": (row.get("FullSubjectTitle") or "").strip(),
                    "title": (row.get("Title") or "").strip(),
                }
            )

        days.append(
            {
                "day": day_name,
                "formatted_date": formatted_date,
                "lesson_plans": lesson_plans_out,
                "schedule": schedule_out,
            }
        )

        for lesson in lesson_plans_out:
            items.append(
                {
                    "type": "day",
                    "day": day_name,
                    "formatted_date": formatted_date,
                    "subject": lesson.get("subject"),
                    "content_text": lesson.get("content_text"),
                }
            )

    return {
        "title": title,
        "week": formatted_week or weekplan_id,
        "url": url,
        "class_or_group": class_or_group,
        "items": items,
        "days": days,
    }


def _clean_text(txt: str) -> str:
    return (txt or "").replace("\xa0", " ").strip()


def _normalize_subject(s: str) -> str:
    s = (s or "").strip().replace(":", "")
    if not s:
        return ""
    return s.lower().capitalize()


def _ensure_subject(s: str | None) -> str:
    s2 = _normalize_subject(s or "")
    return s2 if s2 else "Ukendt"


def _parse_lektiebog_table_rows(table: Any, dato: str) -> list[dict[str, Any]]:
    """Parser en 'Lektiebog'-tabel (FAG/LEKTIER-kolonner) til homework-items."""
    items: list[dict[str, Any]] = []

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        fag_cell, content_cell = cells[0], cells[1]
        fag_text = _clean_text(fag_cell.get_text(" ", strip=True))

        if fag_cell.name == "th" or fag_text.lower() in ("fag", "lektier"):
            continue

        links: list[dict[str, Any]] = []
        for a in content_cell.find_all("a"):
            t = _clean_text(a.get_text(strip=True)) or "link"
            u = a.get("href")
            links.append({"tekst": t, "url": u})
            a.extract()

        tekst = _clean_text(content_cell.get_text(" ", strip=True))
        if not tekst and not links:
            continue

        items.append(
            {
                "dato": dato,
                "fag": _ensure_subject(fag_text),
                "tekst": tekst,
                "links": links,
            }
        )

    return items


def _parse_homework_notes(html_text: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    result: list[dict[str, Any]] = []

    for li in soup.select("ul.sk-list > li"):
        dato_tag = li.select_one("div.sk-white-box > b")
        content_div = li.select_one("div.sk-user-input")

        if not dato_tag or not content_div:
            continue

        dato = dato_tag.get_text(strip=True).replace(":", "").strip()

        table = content_div.find("table")
        if table:
            result.extend(_parse_lektiebog_table_rows(table, dato))
            continue

        current_fag: str | None = None
        blocks: dict[str | None, dict[str, Any]] = {}

        def ensure_block(fag: str | None) -> dict[str, Any]:
            if fag not in blocks:
                blocks[fag] = {"lines": [], "links": []}
            return blocks[fag]

        for node in content_div.children:
            if getattr(node, "name", None) is None:
                continue

            strong = node.find("strong") if hasattr(node, "find") else None
            if strong:
                fag_txt = _normalize_subject(_clean_text(strong.get_text(strip=True)))
                if fag_txt:
                    current_fag = fag_txt
                    ensure_block(current_fag)
                strong.extract()

            for a in node.find_all("a"):
                t = _clean_text(a.get_text(strip=True)) or "link"
                u = a.get("href")
                ensure_block(current_fag)["links"].append(
                    {"tekst": t, "url": u}
                )
                a.extract()

            txt = _clean_text(node.get_text(" ", strip=True))
            if txt:
                ensure_block(current_fag)["lines"].append(txt)

        for fag, data in blocks.items():
            lines = data.get("lines") or []
            links = data.get("links") or []
            tekst = "\n".join(
                [_clean_text(x) for x in lines if _clean_text(x)]
            ).strip()

            if not tekst and not links:
                continue

            if (not fag or not str(fag).strip()) and tekst:
                first_line = tekst.splitlines()[0].strip()
                m = re.match(r"^([A-Za-zÆØÅæøå ]{2,30})\s*:\s*(.+)$", first_line)
                if m:
                    guessed_fag = _normalize_subject(m.group(1).strip())
                    rest = m.group(2).strip()
                    fag = guessed_fag
                    remaining_lines = tekst.splitlines()[1:]
                    tekst = "\n".join([rest] + remaining_lines).strip()

            fag_final = _ensure_subject(str(fag) if fag is not None else None)

            result.append(
                {
                    "dato": dato,
                    "fag": fag_final,
                    "tekst": tekst,
                    "links": links,
                }
            )

    return result


def _dk_date_to_iso(date_str: str | None) -> str | None:
    if not date_str:
        return None

    s = date_str.strip()
    if "," in s:
        s = s.split(",", 1)[1].strip()

    m = re.match(r"^(\d{1,2})\.\s*([A-Za-zæøåÆØÅ\.]+)\s+(\d{4})$", s)
    if not m:
        return date_str

    day = int(m.group(1))
    mon_raw = m.group(2).lower().replace(".", "").strip()
    year = int(m.group(3))

    months = {
        "jan": 1, "januar": 1,
        "feb": 2, "februar": 2,
        "mar": 3, "marts": 3,
        "apr": 4, "april": 4,
        "maj": 5,
        "jun": 6, "juni": 6,
        "jul": 7, "juli": 7,
        "aug": 8, "august": 8,
        "sep": 9, "september": 9,
        "okt": 10, "oktober": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    month = months.get(mon_raw)
    if not month:
        return date_str

    return f"{year:04d}-{month:02d}-{day:02d}"
