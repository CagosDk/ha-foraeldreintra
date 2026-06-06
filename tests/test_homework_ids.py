from custom_components.foraeldreintra.homework_ids import _normalize, build_homework_id


class TestNormalize:
    def test_empty_string(self):
        assert _normalize("") == ""

    def test_none(self):
        assert _normalize(None) == ""

    def test_strips_whitespace(self):
        assert _normalize("  hello  ") == "hello"

    def test_lowercases(self):
        assert _normalize("HELLO World") == "hello world"

    def test_collapses_internal_whitespace(self):
        assert _normalize("hello   world") == "hello world"

    def test_tab_treated_as_whitespace(self):
        assert _normalize("hello\tworld") == "hello world"

    def test_newline_treated_as_whitespace(self):
        assert _normalize("hello\nworld") == "hello world"


class TestBuildHomeworkId:
    def test_returns_16_char_hex_string(self):
        hw_id = build_homework_id("Anna", "2024-01-15", "Dansk", "Side 42", "Læs kapitel 3", "diary")
        assert len(hw_id) == 16
        assert all(c in "0123456789abcdef" for c in hw_id)

    def test_same_inputs_produce_same_id(self):
        id1 = build_homework_id("Anna", "2024-01-15", "Dansk", "Side 42", "Læs kapitel 3", "diary")
        id2 = build_homework_id("Anna", "2024-01-15", "Dansk", "Side 42", "Læs kapitel 3", "diary")
        assert id1 == id2

    def test_different_child_name_gives_different_id(self):
        id1 = build_homework_id("Anna", "2024-01-15", "Dansk", "Side 42", "Læs", "diary")
        id2 = build_homework_id("Bo", "2024-01-15", "Dansk", "Side 42", "Læs", "diary")
        assert id1 != id2

    def test_different_subject_gives_different_id(self):
        id1 = build_homework_id("Anna", "2024-01-15", "Dansk", "Side 42", "Læs", "diary")
        id2 = build_homework_id("Anna", "2024-01-15", "Matematik", "Side 42", "Læs", "diary")
        assert id1 != id2

    def test_different_date_gives_different_id(self):
        id1 = build_homework_id("Anna", "2024-01-15", "Dansk", "Side 42", "Læs", "diary")
        id2 = build_homework_id("Anna", "2024-01-16", "Dansk", "Side 42", "Læs", "diary")
        assert id1 != id2

    def test_case_differences_are_ignored(self):
        id1 = build_homework_id("Anna", "2024-01-15", "DANSK", "SIDE 42", "LÆS", "diary")
        id2 = build_homework_id("Anna", "2024-01-15", "dansk", "side 42", "læs", "diary")
        assert id1 == id2

    def test_extra_whitespace_is_ignored(self):
        id1 = build_homework_id("Anna", "2024-01-15", "Dansk", "Side  42", "Læs  kapitel", "diary")
        id2 = build_homework_id("Anna", "2024-01-15", "Dansk", "Side 42", "Læs kapitel", "diary")
        assert id1 == id2

    def test_none_values_do_not_raise(self):
        hw_id = build_homework_id(None, None, None, None, None, None)
        assert len(hw_id) == 16

    def test_different_source_gives_different_id(self):
        id1 = build_homework_id("Anna", "2024-01-15", "Dansk", "Side 42", "Læs", "diary")
        id2 = build_homework_id("Anna", "2024-01-15", "Dansk", "Side 42", "Læs", "weekplan")
        assert id1 != id2
