import pytest

from custom_components.foraeldreintra.formatting import (
    _apply_subject_alias,
    _build_display_title,
    _build_homework_markdown,
    _build_weekplan_markdown,
    _combine_schedule_rows,
    _derive_homework_title_from_prefix,
    _expand_formatted_date,
    _extract_practice_text_from_general_content,
    _extract_year_from_weekplan,
    _format_day_header,
    _format_general_content,
    _formatted_date_to_iso,
    _is_secondary_subject,
    _lesson_matches_practice_marker,
    _looks_like_date_heading,
    _normalize_subject_value,
    _parse_iso_date,
    _parse_keyword_lines,
    _parse_subject_aliases,
    _plan_focus_only,
    _plan_general_only,
    _plan_schedule_only,
    _pretty_title_case,
    _week_short,
    SECONDARY_SUBJECTS,
    STANDARD_SUBJECT_ALIASES,
)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

class TestParseIsoDate:
    def test_valid_iso_date(self):
        from datetime import date
        assert _parse_iso_date("2024-01-15") == date(2024, 1, 15)

    def test_none_returns_none(self):
        assert _parse_iso_date(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_iso_date("") is None

    def test_invalid_format_returns_none(self):
        assert _parse_iso_date("15-01-2024") is None


class TestExtractYearFromWeekplan:
    def test_extracts_from_week_field(self):
        assert _extract_year_from_weekplan({"week": "23-2024"}) == 2024

    def test_extracts_from_url(self):
        assert _extract_year_from_weekplan({"url": "/item/class/05-2025"}) == 2025

    def test_extracts_four_digit_year_from_title(self):
        assert _extract_year_from_weekplan({"title": "Ugeplan 2024"}) == 2024

    def test_returns_none_when_no_year(self):
        assert _extract_year_from_weekplan({"title": "Ingen år her"}) is None

    def test_empty_plan_returns_none(self):
        assert _extract_year_from_weekplan({}) is None


class TestFormattedDateToIso:
    def test_short_month_with_year(self):
        assert _formatted_date_to_iso("15. jan", 2024) == "2024-01-15"

    def test_long_month_with_year(self):
        assert _formatted_date_to_iso("3. marts", 2024) == "2024-03-03"

    def test_uses_default_year_when_none(self):
        from datetime import date
        result = _formatted_date_to_iso("5. maj", None)
        assert result is not None
        assert result.endswith("-05-05")

    def test_none_returns_none(self):
        assert _formatted_date_to_iso(None, 2024) is None

    def test_empty_returns_none(self):
        assert _formatted_date_to_iso("", 2024) is None

    def test_unknown_format_returns_none(self):
        assert _formatted_date_to_iso("15 januar 2024", 2024) is None

    def test_unknown_month_returns_none(self):
        assert _formatted_date_to_iso("15. blarg", 2024) is None


class TestExpandFormattedDate:
    def test_expands_abbreviated_month(self):
        assert _expand_formatted_date("15. jan") == "15. januar"

    def test_expands_marts(self):
        assert _expand_formatted_date("3. mar") == "3. marts"

    def test_already_long_month_unchanged(self):
        assert _expand_formatted_date("15. januar") == "15. januar"

    def test_empty_returns_empty(self):
        assert _expand_formatted_date("") == ""

    def test_non_date_format_returned_as_is(self):
        assert _expand_formatted_date("Noget andet") == "Noget andet"


# ---------------------------------------------------------------------------
# Keyword / subject helpers
# ---------------------------------------------------------------------------

class TestParseKeywordLines:
    def test_none_returns_empty_list(self):
        assert _parse_keyword_lines(None) == []

    def test_comma_separated(self):
        assert _parse_keyword_lines("lektier,lektieopgave") == ["lektier", "lektieopgave"]

    def test_semicolon_separated(self):
        assert _parse_keyword_lines("lektier;lektieopgave") == ["lektier", "lektieopgave"]

    def test_newline_separated(self):
        assert _parse_keyword_lines("lektier\nlektieopgave") == ["lektier", "lektieopgave"]

    def test_lowercases_keywords(self):
        assert _parse_keyword_lines("LEKTIER") == ["lektier"]

    def test_strips_whitespace(self):
        assert _parse_keyword_lines("  lektier  ") == ["lektier"]

    def test_empty_entries_skipped(self):
        result = _parse_keyword_lines("lektier,,opgave")
        assert "" not in result
        assert "lektier" in result
        assert "opgave" in result


class TestNormalizeSubjectValue:
    def test_lowercases(self):
        assert _normalize_subject_value("DANSK") == "dansk"

    def test_collapses_whitespace(self):
        assert _normalize_subject_value("Dansk  Litteratur") == "dansk litteratur"

    def test_none_returns_empty(self):
        assert _normalize_subject_value(None) == ""

    def test_strips_whitespace(self):
        assert _normalize_subject_value("  dansk  ") == "dansk"


class TestParseSubjectAliases:
    def test_basic_alias(self):
        result = _parse_subject_aliases("DAN=Dansk")
        assert result["DAN"] == "Dansk"

    def test_multiple_aliases_semicolon(self):
        result = _parse_subject_aliases("DAN=Dansk;MAT=Matematik")
        assert result["DAN"] == "Dansk"
        assert result["MAT"] == "Matematik"

    def test_key_uppercased(self):
        result = _parse_subject_aliases("dan=Dansk")
        assert "DAN" in result

    def test_none_returns_empty_dict(self):
        assert _parse_subject_aliases(None) == {}

    def test_lines_without_equals_ignored(self):
        result = _parse_subject_aliases("ugyldig linje\nDAN=Dansk")
        assert "DAN" in result
        assert len(result) == 1


class TestApplySubjectAlias:
    def test_known_alias_returned(self):
        assert _apply_subject_alias("DAN", {"DAN": "Dansk"}) == "Dansk"

    def test_unknown_label_returned_as_is(self):
        assert _apply_subject_alias("Matematik", {}) == "Matematik"

    def test_case_insensitive_lookup(self):
        assert _apply_subject_alias("dan", {"DAN": "Dansk"}) == "Dansk"

    def test_empty_string_returns_empty(self):
        assert _apply_subject_alias("", {"DAN": "Dansk"}) == ""

    def test_standard_aliases_work(self):
        assert _apply_subject_alias("DAN", STANDARD_SUBJECT_ALIASES) == "Dansk"
        assert _apply_subject_alias("MAT", STANDARD_SUBJECT_ALIASES) == "Matematik"


class TestPrettyTitleCase:
    def test_lowercases_and_capitalises_first(self):
        assert _pretty_title_case("DANSK") == "Dansk"

    def test_already_correct_unchanged(self):
        assert _pretty_title_case("Dansk") == "Dansk"

    def test_empty_string(self):
        assert _pretty_title_case("") == ""


# ---------------------------------------------------------------------------
# Derived homework helpers
# ---------------------------------------------------------------------------

class TestDeriveHomeworkTitleFromPrefix:
    def test_diktat_prefix(self):
        assert _derive_homework_title_from_prefix("Diktatord") == "Diktatord"

    def test_laes_prefix(self):
        assert _derive_homework_title_from_prefix("Læseopgave") == "Læsning"

    def test_generic_prefix(self):
        assert _derive_homework_title_from_prefix("Opgave") == "Opgave"

    def test_empty_returns_lektie(self):
        assert _derive_homework_title_from_prefix("") == "Lektie"

    def test_strips_trailing_colon(self):
        assert _derive_homework_title_from_prefix("Opgave:") == "Opgave"


class TestExtractPracticeTextFromGeneralContent:
    def test_finds_word_list_after_colon(self):
        content = "Diktatord: hund, kat, fugl, hest, bi"
        result = _extract_practice_text_from_general_content(content, ["diktat"])
        assert result is not None
        title, words = result
        assert "diktat" in title.lower() or title == "Diktatord"
        assert "hund" in words

    def test_returns_none_when_no_keyword_match(self):
        content = "Noget tekst uden relevante nøgleord"
        result = _extract_practice_text_from_general_content(content, ["diktat"])
        assert result is None

    def test_returns_none_for_empty_content(self):
        assert _extract_practice_text_from_general_content("", ["diktat"]) is None

    def test_returns_none_for_empty_keywords(self):
        content = "Diktatord: hund, kat, fugl, hest"
        assert _extract_practice_text_from_general_content(content, []) is None

    def test_requires_at_least_three_words_in_list(self):
        content = "Diktatord: hund, kat"
        result = _extract_practice_text_from_general_content(content, ["diktat"])
        assert result is None


class TestLessonMatchesPracticeMarker:
    def test_matches_by_title(self):
        assert _lesson_matches_practice_marker("Husk diktatord til fredag", "Diktatord", []) is True

    def test_matches_diktatord_special_case(self):
        assert _lesson_matches_practice_marker("Husk diktat", "Diktatord", []) is True

    def test_matches_by_keyword(self):
        assert _lesson_matches_practice_marker("Lær ordene", "", ["lær"]) is True

    def test_no_match(self):
        assert _lesson_matches_practice_marker("Andet indhold", "Diktatord", ["lektie"]) is False

    def test_empty_lesson_text(self):
        assert _lesson_matches_practice_marker("", "Diktatord", ["diktat"]) is False


# ---------------------------------------------------------------------------
# Schedule formatting
# ---------------------------------------------------------------------------

class TestIsSecondarySubject:
    def test_known_secondary_subjects(self):
        for subj in SECONDARY_SUBJECTS:
            assert _is_secondary_subject(subj) is True

    def test_primary_subject(self):
        assert _is_secondary_subject("Dansk") is False

    def test_empty_string(self):
        assert _is_secondary_subject("") is True


class TestCombineScheduleRows:
    def test_combines_same_time_slot(self):
        rows = [
            {"time": "08:00", "subject_short": "DAN", "subject_full": "Dansk", "title": ""},
            {"time": "08:00", "subject_short": "MAT", "subject_full": "Matematik", "title": ""},
        ]
        result = _combine_schedule_rows(rows, {})
        assert len(result) == 1
        assert "Dansk" in result[0]
        assert "Matematik" in result[0]

    def test_empty_rows_returns_empty_list(self):
        assert _combine_schedule_rows([], {}) == []

    def test_applies_alias(self):
        rows = [{"time": "08:00", "subject_short": "DAN", "subject_full": "", "title": ""}]
        result = _combine_schedule_rows(rows, {"DAN": "Dansk"})
        assert "Dansk" in result[0]

    def test_duplicate_entries_not_repeated(self):
        rows = [
            {"time": "08:00", "subject_short": "DAN", "subject_full": "Dansk", "title": ""},
            {"time": "08:00", "subject_short": "DAN", "subject_full": "Dansk", "title": ""},
        ]
        result = _combine_schedule_rows(rows, {})
        assert result[0].count("Dansk") == 1


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

class TestWeekShort:
    def test_extracts_week_number(self):
        assert _week_short("23-2024") == "23"

    def test_removes_leading_zero(self):
        assert _week_short("05-2024") == "5"

    def test_non_standard_format_returned_as_is(self):
        assert _week_short("uge 23") == "uge 23"

    def test_none_returns_empty(self):
        assert _week_short(None) == ""

    def test_empty_returns_empty(self):
        assert _week_short("") == ""


class TestBuildDisplayTitle:
    def test_class_and_week(self):
        plan = {"class_or_group": "3A", "week": "23-2024"}
        assert _build_display_title(plan) == "Ugeplan for 3A - uge 23"

    def test_week_only(self):
        plan = {"class_or_group": "", "week": "23-2024"}
        assert _build_display_title(plan) == "Ugeplan - uge 23"

    def test_fallback_to_title(self):
        plan = {"class_or_group": "", "week": "", "title": "Min ugeplan"}
        assert _build_display_title(plan) == "Min ugeplan"

    def test_empty_plan(self):
        assert _build_display_title({}) == ""


class TestFormatDayHeader:
    def test_day_with_date(self):
        result = _format_day_header({"day": "Mandag", "formatted_date": "15. jan"})
        assert result == "Mandag 15. januar"

    def test_day_without_date(self):
        result = _format_day_header({"day": "Mandag", "formatted_date": ""})
        assert result == "Mandag"

    def test_empty_day(self):
        result = _format_day_header({"day": "", "formatted_date": ""})
        assert result == ""


class TestLooksLikeDateHeading:
    def test_weekday_with_colon(self):
        assert _looks_like_date_heading("Mandag:") is True

    def test_weekday_with_date_and_colon(self):
        assert _looks_like_date_heading("Tirsdag, 15. januar:") is True

    def test_no_colon(self):
        assert _looks_like_date_heading("Mandag") is False

    def test_non_weekday(self):
        assert _looks_like_date_heading("Emne:") is False


class TestFormatGeneralContent:
    def test_plain_text_returned(self):
        assert _format_general_content("Hej verden") == "Hej verden"

    def test_empty_returns_empty(self):
        assert _format_general_content("") == ""

    def test_weekday_heading_promoted_to_h3(self):
        result = _format_general_content("Mandag:\nHusk lektier")
        assert "### Mandag:" in result

    def test_long_colon_line_promoted_to_h3(self):
        result = _format_general_content("Dette er en lang overskrift med kolon:")
        assert "### Dette er en lang overskrift med kolon:" in result


# ---------------------------------------------------------------------------
# Plan slice helpers
# ---------------------------------------------------------------------------

SAMPLE_PLAN = {
    "title": "Ugeplan",
    "week": "23-2024",
    "url": "https://example.com",
    "class_or_group": "3A",
    "items": [
        {"type": "general", "subject": "Dansk", "content_text": "Læs side 42"},
        {"type": "day", "subject": "Matematik", "content_text": "Opgave 5"},
    ],
    "days": [
        {
            "day": "Mandag",
            "formatted_date": "15. jan",
            "lesson_plans": [{"subject": "Fokus", "content_text": "Fokusemne"}],
            "schedule": [{"time": "08:00", "subject_short": "DAN", "subject_full": "Dansk", "title": ""}],
        }
    ],
}


class TestPlanGeneralOnly:
    def test_keeps_only_general_items(self):
        result = _plan_general_only(SAMPLE_PLAN)
        assert all(item["type"] == "general" for item in result["items"])

    def test_days_is_empty(self):
        result = _plan_general_only(SAMPLE_PLAN)
        assert result["days"] == []

    def test_preserves_metadata(self):
        result = _plan_general_only(SAMPLE_PLAN)
        assert result["week"] == "23-2024"
        assert result["class_or_group"] == "3A"


class TestPlanFocusOnly:
    def test_keeps_days_with_lesson_plans(self):
        result = _plan_focus_only(SAMPLE_PLAN)
        assert len(result["days"]) == 1
        assert result["days"][0]["lesson_plans"]

    def test_schedule_cleared_from_days(self):
        result = _plan_focus_only(SAMPLE_PLAN)
        assert result["days"][0]["schedule"] == []

    def test_items_is_empty(self):
        result = _plan_focus_only(SAMPLE_PLAN)
        assert result["items"] == []


class TestPlanScheduleOnly:
    def test_keeps_days_with_schedule(self):
        result = _plan_schedule_only(SAMPLE_PLAN)
        assert len(result["days"]) == 1
        assert result["days"][0]["schedule"]

    def test_lesson_plans_cleared_from_days(self):
        result = _plan_schedule_only(SAMPLE_PLAN)
        assert result["days"][0]["lesson_plans"] == []

    def test_items_is_empty(self):
        result = _plan_schedule_only(SAMPLE_PLAN)
        assert result["items"] == []


# ---------------------------------------------------------------------------
# Markdown builders
# ---------------------------------------------------------------------------

class TestBuildHomeworkMarkdown:
    def test_empty_items_returns_no_lektier(self):
        assert _build_homework_markdown([]) == "Ingen lektier fundet."

    def test_single_item_produces_output(self):
        items = [{"dato": "2024-01-15", "barn": "Anna", "fag": "Dansk", "tekst": "Læs side 42", "links": []}]
        result = _build_homework_markdown(items)
        assert "Anna" in result
        assert "Dansk" in result
        assert "Læs side 42" in result

    def test_items_without_tekst_or_links_skipped(self):
        items = [{"dato": "2024-01-15", "barn": "Anna", "fag": "Dansk", "tekst": "", "links": []}]
        result = _build_homework_markdown(items)
        assert result == "Ingen lektier fundet."

    def test_dates_sorted_chronologically(self):
        items = [
            {"dato": "2024-01-20", "barn": "Anna", "fag": "Matematik", "tekst": "Side 10", "links": []},
            {"dato": "2024-01-15", "barn": "Anna", "fag": "Dansk", "tekst": "Side 42", "links": []},
        ]
        result = _build_homework_markdown(items)
        # Dates are rendered as Danish headers, so d.15. appears before d.20.
        assert result.index("d.15.") < result.index("d.20.")

    def test_derived_item_shows_source(self):
        items = [{"dato": "2024-01-15", "barn": "Anna", "fag": "Dansk", "tekst": "Ord", "links": [], "derived": True}]
        result = _build_homework_markdown(items)
        assert "ugeplan" in result.lower()


class TestBuildWeekplanMarkdown:
    def test_empty_plan_returns_ingen_ugeplan(self):
        result = _build_weekplan_markdown(
            {"title": "", "week": "", "class_or_group": "", "items": [], "days": []},
            include_general=True, include_focus=True, include_schedule=True, alias_map={},
        )
        assert result == "Ingen ugeplan fundet."

    def test_title_in_output(self):
        plan = {"title": "Ugeplan 23", "week": "23-2024", "class_or_group": "3A", "items": [], "days": []}
        result = _build_weekplan_markdown(plan, True, True, True, {})
        assert "3A" in result
        assert "23" in result

    def test_general_items_shown_when_enabled(self):
        plan = {
            "title": "", "week": "23-2024", "class_or_group": "",
            "items": [{"type": "general", "subject": "Dansk", "content_text": "Tekst"}],
            "days": [],
        }
        result = _build_weekplan_markdown(plan, include_general=True, include_focus=False, include_schedule=False, alias_map={})
        assert "Dansk" in result
        assert "Tekst" in result

    def test_general_items_hidden_when_disabled(self):
        plan = {
            "title": "", "week": "23-2024", "class_or_group": "",
            "items": [{"type": "general", "subject": "Dansk", "content_text": "Hemmelig tekst"}],
            "days": [],
        }
        result = _build_weekplan_markdown(plan, include_general=False, include_focus=False, include_schedule=False, alias_map={})
        assert "Hemmelig tekst" not in result
