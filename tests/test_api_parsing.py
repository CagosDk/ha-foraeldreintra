import html as html_module
import json

import pytest

from custom_components.foraeldreintra.api_parser import (
    _clean_child_name,
    _dk_date_to_iso,
    _extract_diary_id,
    _extract_latest_weekplan_from_list,
    _html_to_text,
    _parse_homework_notes,
    _parse_weekplan_page,
)


class TestDkDateToIso:
    def test_full_danish_date(self):
        assert _dk_date_to_iso("15. januar 2024") == "2024-01-15"

    def test_date_with_day_name_prefix(self):
        assert _dk_date_to_iso("mandag, 15. januar 2024") == "2024-01-15"

    def test_abbreviated_month(self):
        assert _dk_date_to_iso("3. feb 2024") == "2024-02-03"

    def test_single_digit_day_is_zero_padded(self):
        assert _dk_date_to_iso("5. maj 2024") == "2024-05-05"

    def test_none_returns_none(self):
        assert _dk_date_to_iso(None) is None

    def test_empty_string_returns_none(self):
        assert _dk_date_to_iso("") is None

    def test_unrecognised_format_returns_original(self):
        assert _dk_date_to_iso("invalid date") == "invalid date"

    @pytest.mark.parametrize("month_name,expected_num", [
        ("januar", 1), ("februar", 2), ("marts", 3), ("april", 4),
        ("maj", 5), ("juni", 6), ("juli", 7), ("august", 8),
        ("september", 9), ("oktober", 10), ("november", 11), ("december", 12),
    ])
    def test_all_danish_month_names(self, month_name, expected_num):
        result = _dk_date_to_iso(f"1. {month_name} 2024")
        assert result == f"2024-{expected_num:02d}-01"

    @pytest.mark.parametrize("abbrev,expected_num", [
        ("jan", 1), ("feb", 2), ("mar", 3), ("apr", 4),
        ("jun", 6), ("jul", 7), ("aug", 8), ("sep", 9),
        ("okt", 10), ("nov", 11), ("dec", 12),
    ])
    def test_abbreviated_month_names(self, abbrev, expected_num):
        result = _dk_date_to_iso(f"1. {abbrev} 2024")
        assert result == f"2024-{expected_num:02d}-01"


class TestCleanChildName:
    def test_removes_item_suffix_lowercase(self):
        assert _clean_child_name("AnnaItem") == "Anna"

    def test_removes_item_suffix_uppercase(self):
        assert _clean_child_name("AnnaITEM") == "Anna"

    def test_name_without_item_suffix_unchanged(self):
        assert _clean_child_name("Anna") == "Anna"

    def test_strips_surrounding_whitespace(self):
        assert _clean_child_name("  Anna  ") == "Anna"

    def test_empty_string_stays_empty(self):
        assert _clean_child_name("") == ""


class TestExtractDiaryId:
    def test_extracts_id_from_weeklyplans_url(self):
        html = '<a href="/parent/123/anna/item/weeklyplansandhomework/diary/456">link</a>'
        assert _extract_diary_id(html) == "456"

    def test_extracts_id_from_diary_slash_pattern(self):
        assert _extract_diary_id('href="/diary/789/"') == "789"

    def test_extracts_id_from_diary_quote_pattern(self):
        assert _extract_diary_id('diary/321"') == "321"

    def test_returns_none_when_no_diary_id(self):
        assert _extract_diary_id("<html>ingen dagbog her</html>") is None

    def test_returns_none_for_empty_string(self):
        assert _extract_diary_id("") is None


class TestHtmlToText:
    def test_plain_paragraph(self):
        assert _html_to_text("<p>Hej verden</p>") == "Hej verden"

    def test_br_tag_becomes_newline(self):
        result = _html_to_text("<p>Linje1<br>Linje2</p>")
        assert "Linje1" in result
        assert "Linje2" in result

    def test_empty_input_returns_empty_string(self):
        assert _html_to_text("") == ""

    def test_strips_html_tags(self):
        assert _html_to_text("<p>Fed og kursiv</p>") == "Fed og kursiv"

    def test_non_breaking_space_replaced(self):
        result = _html_to_text("<p>Hej\xa0verden</p>")
        assert "\xa0" not in result

    def test_empty_lines_removed(self):
        result = _html_to_text("<p>A</p><p></p><p>B</p>")
        assert result == "A\nB"


class TestParseHomeworkNotes:
    def test_empty_html_returns_empty_list(self):
        assert _parse_homework_notes("") == []

    def test_parses_single_homework_item(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"><b>Mandag, 15. januar 2024:</b></div>
            <div class="sk-user-input">
              <p><strong>Dansk:</strong></p>
              <p>Læs side 42</p>
            </div>
          </li>
        </ul>
        """
        result = _parse_homework_notes(html)
        assert len(result) == 1
        assert result[0]["dato"] == "Mandag, 15. januar 2024"
        assert result[0]["fag"] == "Dansk"
        assert "Læs side 42" in result[0]["tekst"]
        assert result[0]["links"] == []

    def test_item_without_date_tag_is_skipped(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"></div>
            <div class="sk-user-input"><p>Noget tekst</p></div>
          </li>
        </ul>
        """
        assert _parse_homework_notes(html) == []

    def test_item_without_content_div_is_skipped(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"><b>Dato:</b></div>
          </li>
        </ul>
        """
        assert _parse_homework_notes(html) == []

    def test_links_are_extracted(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"><b>15. januar 2024:</b></div>
            <div class="sk-user-input">
              <p><a href="https://example.com">Klik her</a></p>
            </div>
          </li>
        </ul>
        """
        result = _parse_homework_notes(html)
        assert len(result) == 1
        assert len(result[0]["links"]) == 1
        assert result[0]["links"][0]["url"] == "https://example.com"
        assert result[0]["links"][0]["tekst"] == "Klik her"


class TestExtractLatestWeekplanFromList:
    def test_returns_none_for_html_without_container(self):
        assert _extract_latest_weekplan_from_list("<html></html>") is None

    def test_extracts_first_weekplan_link(self):
        html = """
        <ul class="sk-weekly-plans-list-container">
          <li>
            <a href="/parent/123/anna/item/weeklyplansandhomework/item/class/23-2024">
              Uge 23
            </a>
          </li>
        </ul>
        """
        result = _extract_latest_weekplan_from_list(html)
        assert result is not None
        assert result["weekplan_id"] == "23-2024"
        assert "Uge 23" in result["title"]
        assert "class/23-2024" in result["href"]

    def test_returns_none_when_no_matching_link(self):
        html = """
        <ul class="sk-weekly-plans-list-container">
          <li><a href="/other/path">Noget andet</a></li>
        </ul>
        """
        assert _extract_latest_weekplan_from_list(html) is None

    def test_returns_none_for_empty_string(self):
        assert _extract_latest_weekplan_from_list("") is None


class TestParseWeekplanPage:
    def test_html_without_app_data_returns_fallback(self):
        result = _parse_weekplan_page(
            html_text="<html></html>",
            weekplan_id="23-2024",
            fallback_title="Uge 23",
            url="https://example.com/weekplan",
        )
        assert result["title"] == "Uge 23"
        assert result["week"] == "23-2024"
        assert result["items"] == []
        assert result["days"] == []

    def test_parses_class_and_week_into_title(self):
        app_data = {
            "SelectedPlan": {
                "FormattedWeek": "23",
                "ClassOrGroup": "3A",
                "GeneralPlan": {"LessonPlans": []},
                "DailyPlans": [],
            }
        }
        encoded = html_module.escape(json.dumps(app_data))
        html_text = f'<div id="root" data-clientlogic-settings-weeklyplansapp="{encoded}"></div>'

        result = _parse_weekplan_page(
            html_text=html_text,
            weekplan_id="23-2024",
            fallback_title="Fallback",
            url="https://example.com/weekplan",
        )
        assert "3A" in result["title"]
        assert "23" in result["title"]
        assert result["class_or_group"] == "3A"

    def test_parses_general_lesson_plan(self):
        app_data = {
            "SelectedPlan": {
                "FormattedWeek": "23",
                "ClassOrGroup": "3A",
                "GeneralPlan": {
                    "LessonPlans": [
                        {
                            "Subject": {"FormattedTitle": "Dansk", "Title": "Dansk"},
                            "Content": "<p>Læs kapitlet</p>",
                        }
                    ]
                },
                "DailyPlans": [],
            }
        }
        encoded = html_module.escape(json.dumps(app_data))
        html_text = f'<div id="root" data-clientlogic-settings-weeklyplansapp="{encoded}"></div>'

        result = _parse_weekplan_page(
            html_text=html_text,
            weekplan_id="23-2024",
            fallback_title="Fallback",
            url="https://example.com/weekplan",
        )
        assert len(result["items"]) == 1
        assert result["items"][0]["type"] == "general"
        assert result["items"][0]["subject"] == "Dansk"
        assert "Læs kapitlet" in result["items"][0]["content_text"]

    def test_invalid_json_in_app_data_returns_fallback(self):
        html_text = '<div id="root" data-clientlogic-settings-weeklyplansapp="not-valid-json"></div>'
        result = _parse_weekplan_page(
            html_text=html_text,
            weekplan_id="23-2024",
            fallback_title="Uge 23",
            url="https://example.com/weekplan",
        )
        assert result["title"] == "Uge 23"
        assert result["items"] == []
