from __future__ import annotations

from typing import Any
from urllib.parse import unquote


def _decode_display_value(value: Any) -> Any:
    """Dekoder URL-encoded tekst til læsbar visning."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return unquote(value).strip()


def _decode_link_dict(link: dict[str, Any]) -> dict[str, Any]:
    return {
        **link,
        "tekst": _decode_display_value(link.get("tekst")),
        "url": _decode_display_value(link.get("url")),
    }


def _decode_homework_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "barn": _decode_display_value(item.get("barn")) or "",
        "fag": _decode_display_value(item.get("fag")) or "",
        "tekst": _decode_display_value(item.get("tekst")) or "",
        "title": _decode_display_value(item.get("title")) or "",
        "keyword_match": _decode_display_value(item.get("keyword_match")) or "",
        "weekplan_day": _decode_display_value(item.get("weekplan_day")) or "",
        "weekplan_date": _decode_display_value(item.get("weekplan_date")) or "",
        "source": _decode_display_value(item.get("source")) or item.get("source"),
        "links": [
            _decode_link_dict(link)
            for link in (item.get("links") or [])
            if isinstance(link, dict)
        ],
    }


def _decode_weekplan_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "subject": _decode_display_value(item.get("subject")) or "",
        "type": _decode_display_value(item.get("type")) or item.get("type"),
        "content_text": _decode_display_value(item.get("content_text")) or "",
        "title": _decode_display_value(item.get("title")) or "",
        "url": _decode_display_value(item.get("url")) or item.get("url"),
    }


def _decode_schedule_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "time": _decode_display_value(row.get("time")) or "",
        "subject_short": _decode_display_value(row.get("subject_short")) or "",
        "subject_full": _decode_display_value(row.get("subject_full")) or "",
        "title": _decode_display_value(row.get("title")) or "",
    }


def _decode_weekplan_day(day: dict[str, Any]) -> dict[str, Any]:
    lesson_plans = day.get("lesson_plans") or []
    schedule = day.get("schedule") or []

    decoded_lessons = [
        {
            **lesson,
            "subject": _decode_display_value(lesson.get("subject")) or "",
            "content_text": _decode_display_value(lesson.get("content_text")) or "",
            "title": _decode_display_value(lesson.get("title")) or "",
        }
        for lesson in lesson_plans
        if isinstance(lesson, dict)
    ]

    decoded_schedule = [
        _decode_schedule_row(row)
        for row in schedule
        if isinstance(row, dict)
    ]

    return {
        **day,
        "day": _decode_display_value(day.get("day")) or "",
        "formatted_date": _decode_display_value(day.get("formatted_date")) or "",
        "lesson_plans": decoded_lessons,
        "schedule": decoded_schedule,
    }


def _decode_weekplan(plan: dict[str, Any]) -> dict[str, Any]:
    items = plan.get("items") or []
    days = plan.get("days") or []

    return {
        **plan,
        "title": _decode_display_value(plan.get("title")) or "",
        "week": _decode_display_value(plan.get("week")) or plan.get("week"),
        "url": _decode_display_value(plan.get("url")) or plan.get("url"),
        "class_or_group": _decode_display_value(plan.get("class_or_group")) or "",
        "items": [_decode_weekplan_item(item) for item in items if isinstance(item, dict)],
        "days": [_decode_weekplan_day(day) for day in days if isinstance(day, dict)],
    }
