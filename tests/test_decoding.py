from custom_components.foraeldreintra.decoding import (
    _decode_display_value,
    _decode_homework_item,
    _decode_link_dict,
    _decode_schedule_row,
    _decode_weekplan,
    _decode_weekplan_day,
    _decode_weekplan_item,
)


class TestDecodeDisplayValue:
    def test_none_returns_none(self):
        assert _decode_display_value(None) is None

    def test_non_string_returned_unchanged(self):
        assert _decode_display_value(42) == 42
        assert _decode_display_value(True) is True

    def test_url_encoded_string_decoded(self):
        assert _decode_display_value("Dansk%20Matematik") == "Dansk Matematik"

    def test_strips_surrounding_whitespace(self):
        assert _decode_display_value("  hej  ") == "hej"

    def test_plain_string_unchanged(self):
        assert _decode_display_value("Dansk") == "Dansk"

    def test_empty_string_stays_empty(self):
        assert _decode_display_value("") == ""

    def test_percent_encoded_danish_chars(self):
        result = _decode_display_value("S%C3%B8nderjylland")
        assert result == "Sønderjylland"


class TestDecodeLinkDict:
    def test_decodes_tekst_and_url(self):
        result = _decode_link_dict({"tekst": "Klik%20her", "url": "https://example.com%2Fpath"})
        assert result["tekst"] == "Klik her"
        assert result["url"] == "https://example.com/path"

    def test_preserves_other_fields(self):
        result = _decode_link_dict({"tekst": "Link", "url": "https://x.com", "extra": "data"})
        assert result["extra"] == "data"

    def test_missing_fields_return_none(self):
        result = _decode_link_dict({})
        assert result["tekst"] is None
        assert result["url"] is None


class TestDecodeHomeworkItem:
    def test_decodes_barn_and_fag(self):
        item = {"barn": "Anna%20Larsen", "fag": "Dansk%20og%20Matematik"}
        result = _decode_homework_item(item)
        assert result["barn"] == "Anna Larsen"
        assert result["fag"] == "Dansk og Matematik"

    def test_none_fields_become_empty_string(self):
        result = _decode_homework_item({})
        assert result["barn"] == ""
        assert result["fag"] == ""
        assert result["tekst"] == ""
        assert result["title"] == ""

    def test_links_are_decoded_recursively(self):
        item = {
            "barn": "Anna",
            "links": [{"tekst": "Se%20her", "url": "https://x.com"}],
        }
        result = _decode_homework_item(item)
        assert result["links"][0]["tekst"] == "Se her"

    def test_non_dict_links_are_skipped(self):
        item = {"barn": "Anna", "links": ["not-a-dict", None]}
        result = _decode_homework_item(item)
        assert result["links"] == []

    def test_source_preserved_when_not_string(self):
        item = {"source": "weekplan"}
        result = _decode_homework_item(item)
        assert result["source"] == "weekplan"

    def test_preserves_extra_fields(self):
        item = {"barn": "Anna", "dato": "2024-01-15", "derived": True}
        result = _decode_homework_item(item)
        assert result["dato"] == "2024-01-15"
        assert result["derived"] is True


class TestDecodeWeekplanItem:
    def test_decodes_subject_and_content(self):
        item = {"subject": "Dansk%20litteratur", "content_text": "L%C3%A6s%20kapitel"}
        result = _decode_weekplan_item(item)
        assert result["subject"] == "Dansk litteratur"
        assert result["content_text"] == "Læs kapitel"

    def test_none_fields_become_empty_string(self):
        result = _decode_weekplan_item({})
        assert result["subject"] == ""
        assert result["content_text"] == ""

    def test_type_preserved(self):
        result = _decode_weekplan_item({"type": "general"})
        assert result["type"] == "general"


class TestDecodeScheduleRow:
    def test_decodes_all_fields(self):
        row = {
            "time": "08%3A00-09%3A00",
            "subject_short": "DAN",
            "subject_full": "Dansk%20litteratur",
            "title": "Fagdag",
        }
        result = _decode_schedule_row(row)
        assert result["time"] == "08:00-09:00"
        assert result["subject_full"] == "Dansk litteratur"

    def test_missing_fields_become_empty_string(self):
        result = _decode_schedule_row({})
        assert result["time"] == ""
        assert result["subject_short"] == ""
        assert result["subject_full"] == ""
        assert result["title"] == ""


class TestDecodeWeekplanDay:
    def test_decodes_day_and_date(self):
        day = {"day": "Mandag", "formatted_date": "15.%20jan", "lesson_plans": [], "schedule": []}
        result = _decode_weekplan_day(day)
        assert result["day"] == "Mandag"
        assert result["formatted_date"] == "15. jan"

    def test_lesson_plans_decoded(self):
        day = {
            "day": "Mandag",
            "formatted_date": "15. jan",
            "lesson_plans": [{"subject": "Dansk%20A", "content_text": "Tekst", "title": ""}],
            "schedule": [],
        }
        result = _decode_weekplan_day(day)
        assert result["lesson_plans"][0]["subject"] == "Dansk A"

    def test_non_dict_lesson_plans_skipped(self):
        day = {"day": "Mandag", "formatted_date": "", "lesson_plans": ["not-a-dict"], "schedule": []}
        result = _decode_weekplan_day(day)
        assert result["lesson_plans"] == []


class TestDecodeWeekplan:
    def test_decodes_top_level_fields(self):
        plan = {
            "title": "Ugeplan%20uge%2023",
            "week": "23-2024",
            "url": "https://example.com",
            "class_or_group": "3A",
            "items": [],
            "days": [],
        }
        result = _decode_weekplan(plan)
        assert result["title"] == "Ugeplan uge 23"
        assert result["week"] == "23-2024"
        assert result["class_or_group"] == "3A"

    def test_items_decoded_recursively(self):
        plan = {
            "title": "",
            "items": [{"subject": "Dansk%20A", "type": "general", "content_text": "", "title": "", "url": ""}],
            "days": [],
        }
        result = _decode_weekplan(plan)
        assert result["items"][0]["subject"] == "Dansk A"

    def test_empty_plan_returns_defaults(self):
        result = _decode_weekplan({})
        assert result["title"] == ""
        assert result["items"] == []
        assert result["days"] == []
