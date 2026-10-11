import json
import re
from pathlib import Path

import pytest

import quizgen.validate as validate_mod
from quizgen.validate import (IMAGE_TYPES, discover, is_remote_image, load_collection,
                              load_quiz)

FIX = Path(__file__).parent / "fixtures"
EXAMPLES = Path(__file__).parent.parent / "examples"


def errors_of(name: str, **kw) -> list[str]:
    return [str(e) for e in load_quiz(FIX / name, **kw).errors]


def warnings_of(name: str) -> list[str]:
    return [str(w) for w in load_quiz(FIX / name).warnings]


def has(lines: list[str], *parts: str) -> bool:
    return any(all(p in line for p in parts) for line in lines)


# One invalid fixture per rule: (file, JSON path, message fragment)
ERROR_CASES = [
    ("rule01-bad-json.json", "", "not valid JSON at line 3"),
    ("rule02-unknown-field.json", "questions[0].options[0].corect", 'unknown field "corect" (did you mean "correct"?)'),
    ("rule02-missing-title.json", "title", 'missing required field "title"'),
    ("rule02-wrong-type.json", "feedback", 'must be one of: "immediate", "end"'),
    ("rule02-wrong-type.json", "shuffle_options", "must be true or false"),
    ("rule02-wrong-type.json", "questions_per_quiz", "must be at least 1"),
    ("rule03-no-correct.json", "questions[0].options", "exactly one option must have"),
    ("rule03-two-correct.json", "questions[1].options", "(found 2)"),
    ("rule04-one-option.json", "questions[1].options", "needs at least 2 entries"),
    ("rule04-empty-option.json", "questions[0].options[1]", 'needs a "text", an "image", or both'),
    ("rule05-m-too-big.json", "questions_per_quiz", "only has 2 questions"),
    ("rule06-missing-translation.json", "questions[1].text", 'missing translation "it"'),
    ("rule06-empty-translation.json", "title", 'missing translation "it"'),
    ("rule06-plain-string.json", "description", '{"any": "..."}'),
    ("rule06-unknown-language.json", "title.fr", 'unknown language "fr"'),
    ("rule06-any-reserved.json", "languages[1]", '"any" is reserved'),
    ("rule07-map-without-languages.json", "title", 'need a "languages" field'),
    ("rule08-both-language-fields.json", "language", "not both"),
    ("rule09-unknown-ui-language.json", "language", 'no built-in interface translation for "xx"'),
    ("rule10-image-missing.json", "questions[0].image", "image file not found"),
    ("rule10-image-parent.json", "questions[0].image", "no \"..\""),
    ("rule10-image-absolute.json", "questions[0].image", "not absolute"),
    ("rule10-image-scheme.json", "questions[0].image", "http(s)://"),
    ("rule11-author-no-name.json", "author.name", 'missing required field "name"'),
    ("rule11-author-bad-url.json", "author.url", "http://"),
    ("rule11-author-bad-email.json", "author.email", "name@example.org"),
    ("rule12-ui-unknown-key.json", "ui.strat", 'did you mean "start"'),
    ("rule12-ui-name-not-allowed.json", "ui.flag", "unknown text key"),
    ("rule12-ui-unknown-message.json", "ui.messages.grate", 'did you mean "great"'),
    ("rule12-ui-language-not-in-quiz.json", "ui.start.de", 'unknown language "de"'),
    ("rule12-ui-string-in-multi.json", "ui.start", "must be a map"),
    ("rule12-ui-map-in-single.json", "ui.start", 'need a "languages" field'),
    ("rule12-ui-empty-string.json", "ui.start", "must not be empty"),
    ("rule12-ui-bad-placeholder.json", "ui.correct", "{name} cannot be used here"),
]


@pytest.mark.parametrize("name,path,fragment", ERROR_CASES)
def test_error_rules(name, path, fragment):
    lines = errors_of(name)
    assert has(lines, f": {path}: " if path else name, fragment), lines


def test_errors_are_collected_together():
    assert len(errors_of("rule02-wrong-type.json")) == 3


def test_result_has_no_quiz_on_errors():
    assert load_quiz(FIX / "rule03-no-correct.json").quiz is None


def test_m_override_too_big():
    result = load_quiz(FIX / "valid-minimal.json", questions_override=5)
    assert has([str(e) for e in result.errors], "--questions is 5")


def test_missing_file():
    assert has(errors_of("does-not-exist.json"), "cannot read file")


@pytest.mark.parametrize("name,fragment", [
    ("warn-m-equals-n.json", "all 2 questions"),
    ("warn-duplicate-options.json", 'duplicate option text'),
    ("warn-any-unused.json", '"any" is never used'),
    ("warn-ui-missing-placeholder.json", "{total}"),
])
def test_warnings(name, fragment):
    assert has(warnings_of(name), fragment)
    assert errors_of(name) == []


def test_valid_has_no_warnings():
    result = load_quiz(FIX / "valid-minimal.json")
    assert result.errors == [] and result.warnings == []


# ---- normalisation -------------------------------------------------------


def test_single_language_becomes_multi_form():
    quiz = load_quiz(FIX / "valid-minimal.json").quiz
    assert quiz["languages"] == ["en"]
    assert "language" not in quiz
    assert quiz["title"] == {"en": "T"}
    assert quiz["questions"][0]["options"][0] == {"text": {"en": "A"}, "correct": True}
    assert quiz["questions"][0]["options"][1]["correct"] is False


def test_defaults_filled():
    quiz = load_quiz(FIX / "valid-minimal.json").quiz
    assert quiz["feedback"] == "immediate"
    assert quiz["shuffle_options"] is True
    assert quiz["ui"] == {}
    assert quiz["questions_per_quiz"] == 1  # as set in the fixture


def test_default_m_is_min_of_ten_and_n(tmp_path):
    f = tmp_path / "q.json"
    f.write_text(json.dumps({"title": "T", "questions": [
        {"text": "Q", "options": [{"text": "A", "correct": True}, {"text": "B"}]}]}))
    result = load_quiz(f)
    assert result.errors == [] and result.warnings == []
    assert result.quiz["questions_per_quiz"] == 1


def test_single_language_uses_language_field(tmp_path):
    f = tmp_path / "q.json"
    f.write_text(json.dumps({"title": "Titolo", "language": "it", "questions_per_quiz": 1, "questions": [
        {"text": "D", "options": [{"text": "A", "correct": True}, {"text": "B"}]},
        {"text": "E", "options": [{"text": "A", "correct": True}, {"text": "B"}]}]}))
    quiz = load_quiz(f).quiz
    assert quiz["languages"] == ["it"] and quiz["title"] == {"it": "Titolo"}


def test_any_expansion_and_locale_override(tmp_path):
    f = tmp_path / "q.json"
    f.write_text(json.dumps({
        "title": {"any": "Quiz", "it": "Quiz italiano"},
        "languages": ["en", "it"],
        "questions": [{"text": {"any": "Q"}, "options": [
            {"text": {"any": "Rome", "it": "Roma"}, "correct": True}, {"text": {"any": "12"}}]}],
    }))
    result = load_quiz(f)
    assert result.errors == []
    quiz = result.quiz
    assert quiz["title"] == {"en": "Quiz", "it": "Quiz italiano"}
    assert quiz["questions"][0]["options"][0]["text"] == {"en": "Rome", "it": "Roma"}
    assert quiz["questions"][0]["options"][1]["text"] == {"en": "12", "it": "12"}
    assert quiz["questions_per_quiz"] == 1


def test_override_applied():
    quiz = load_quiz(FIX / "valid-minimal.json", questions_override=2).quiz
    assert quiz["questions_per_quiz"] == 2


def test_ui_normalisation():
    quiz = load_quiz(FIX / "valid-ui.json").quiz
    assert quiz["ui"] == {
        "start": {"en": "Go!", "it": "Via!"},
        "next": {"it": "Avanti"},
        "messages": {"great": {"en": "Wow"}},
    }


def test_ui_single_language_string(tmp_path):
    f = tmp_path / "q.json"
    f.write_text(json.dumps({"title": "T", "language": "it", "ui": {"start": "Via!", "messages": {"good": "Bene"}},
                             "questions": [{"text": "Q", "options": [{"text": "A", "correct": True}, {"text": "B"}]}]}))
    assert load_quiz(f).quiz["ui"] == {"start": {"it": "Via!"}, "messages": {"good": {"it": "Bene"}}}


def test_author_kept():
    quiz = load_quiz(FIX / "valid-minimal.json").quiz
    assert "author" not in quiz


# ---- images --------------------------------------------------------------


def test_local_and_remote_images_ok(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    f = tmp_path / "q.json"
    f.write_text(json.dumps({"title": "T", "questions": [{
        "text": "Q", "image": "images/a.png", "options": [
            {"text": "A", "correct": True, "image": "https://example.org/a.png"}, {"image": "images/a.png"}]}]}))
    result = load_quiz(f)
    assert result.errors == []
    assert result.quiz["questions"][0]["options"][1] == {"image": "images/a.png", "correct": False}


def test_symlink_escaping_directory_rejected(tmp_path):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"x")
    quiz_dir = tmp_path / "quiz"
    quiz_dir.mkdir()
    (quiz_dir / "link.png").symlink_to(outside)
    f = quiz_dir / "q.json"
    f.write_text(json.dumps({"title": "T", "questions": [{
        "text": "Q", "image": "link.png", "options": [{"text": "A", "correct": True}, {"text": "B"}]}]}))
    assert has([str(e) for e in load_quiz(f).errors], "no \"..\"")


# ---- collections ---------------------------------------------------------


def test_valid_collection():
    result = load_collection(FIX / "collection-valid.json")
    assert result.errors == [] and result.quiz["author"]["name"] == "Ann"


def test_collection_bad_author():
    result = load_collection(FIX / "collection-bad-author.json")
    assert has([str(e) for e in result.errors], "author.email")


def test_collection_ui():
    result = load_collection(FIX / "collection-ui.json")
    assert result.errors == []
    assert result.quiz["ui"] == {
        "start": {"any": "Go"},
        "next": {"it": "Avanti", "any": "Next"},
        "messages": {"good": {"any": "Nice"}},
    }


def test_collection_ui_bad():
    lines = [str(e) for e in load_collection(FIX / "collection-ui-bad.json").errors]
    assert has(lines, "ui.start.xx", "unknown language")
    assert has(lines, "ui.wrongg", "unknown text key")
    assert has(lines, "ui.finish", "must not be empty")


# ---- examples and discovery ------------------------------------------------


@pytest.mark.parametrize("name", ["farm-animals.json", "times-tables.json"])
def test_examples_are_clean(name):
    result = load_quiz(EXAMPLES / name)
    assert result.errors == [] and result.warnings == []


def test_discover(tmp_path):
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "schema.json").write_text("{}")
    sub = tmp_path / "school"
    sub.mkdir()
    (sub / "b.json").write_text("{}")
    (sub / "collection.json").write_text("{}")
    deep = sub / "deeper"
    deep.mkdir()
    (deep / "c.json").write_text("{}")
    files, problems = discover(tmp_path)
    assert [p.relative_to(tmp_path).as_posix() for p in files] == ["a.json", "school/b.json", "school/collection.json"]
    assert problems == []


# ---- review fixes ----------------------------------------------------------

QUESTION = {"text": "Q", "options": [{"text": "A", "correct": True}, {"text": "B"}]}


def quiz_file(tmp_path, **overrides):
    data = {"title": "T", "questions": [QUESTION]}
    data.update(overrides)
    f = tmp_path / "q.json"
    f.write_text(json.dumps(data))
    return f


def raw_file(tmp_path, text, name="q.json"):
    f = tmp_path / name
    f.write_text(text, encoding="utf-8", errors="surrogatepass")
    return f


def msgs(result):
    return [str(e) for e in result.errors]


def test_json_null_is_an_error(tmp_path):
    result = load_quiz(raw_file(tmp_path, "null"))
    assert has(msgs(result), "must be an object")
    assert load_collection(raw_file(tmp_path, "null", "c.json")).errors


def test_deep_nesting_does_not_crash(tmp_path):
    result = load_quiz(raw_file(tmp_path, "[" * 200000 + "]" * 200000))
    assert has(msgs(result), "too deeply nested")
    result = load_quiz(raw_file(tmp_path, '{"a":' * 100000 + "1" + "}" * 100000))
    assert result.errors


def test_huge_number_does_not_crash(tmp_path):
    result = load_quiz(raw_file(tmp_path, '{"title": "T", "questions_per_quiz": ' + "9" * 5000 + "}"))
    assert result.errors


def test_big_file_rejected(tmp_path):
    f = raw_file(tmp_path, '{"title": "' + "a" * (5 * 1024 * 1024) + '"}')
    assert has(msgs(load_quiz(f)), "too large")


def test_very_long_image_name_does_not_crash(tmp_path):
    f = quiz_file(tmp_path, questions=[{**QUESTION, "image": "a" * 300 + ".png"}])
    assert has(msgs(load_quiz(f)), "questions[0].image", "not found")


def test_lone_surrogate_rejected(tmp_path):
    f = raw_file(tmp_path, '{"title": "T", "\\ud800": 1, "questions": []}'.replace("\\", "\\"))
    result = load_quiz(f)
    assert has(msgs(result), "invalid character")


@pytest.mark.parametrize("url", [
    "https://exa\nmple.org", 'https://exa"mple.org', "https://exa<mple.org", "https://exa\u200bmple.org",
    "javascript:alert(1)", "https://", "ftp://example.org", "https://a b.org",
])
def test_bad_author_urls(tmp_path, url):
    f = quiz_file(tmp_path, author={"name": "Ann", "url": url})
    assert has(msgs(load_quiz(f)), "author.url")


@pytest.mark.parametrize("email", [
    "a@b.co?subject=hi", "javascript:a@b.co", "a@b", "a b@c.org", "a@b.co\nx", "<a>@b.co",
])
def test_bad_author_emails(tmp_path, email):
    f = quiz_file(tmp_path, author={"name": "Ann", "email": email})
    assert has(msgs(load_quiz(f)), "author.email")


def test_author_values_are_stripped(tmp_path):
    f = quiz_file(tmp_path, author={"name": " Ann ", "url": " HTTPS://example.org/x ", "email": " a@b.org "})
    result = load_quiz(f)
    assert result.errors == []
    assert result.quiz["author"] == {"name": "Ann", "url": "HTTPS://example.org/x", "email": "a@b.org"}


@pytest.mark.parametrize("name", ["pic.svg", "data.json", "notes.txt", "noext", "pic.png.exe"])
def test_local_image_types(tmp_path, name):
    (tmp_path / name).write_text("x")
    f = quiz_file(tmp_path, questions=[{**QUESTION, "image": name}])
    assert has(msgs(load_quiz(f)), "local images must be one of")


def test_svg_hint(tmp_path):
    (tmp_path / "a.svg").write_text("<svg/>")
    f = quiz_file(tmp_path, questions=[{**QUESTION, "image": "a.svg"}])
    assert has(msgs(load_quiz(f)), "link to the SVG")


@pytest.mark.parametrize("ext", sorted(IMAGE_TYPES) + [".PNG", ".JpG"])
def test_allowed_image_types(tmp_path, ext):
    (tmp_path / f"a{ext}").write_bytes(b"x")
    f = quiz_file(tmp_path, questions=[{**QUESTION, "image": f"a{ext}"}])
    assert load_quiz(f).errors == []


def test_is_remote_image():
    assert is_remote_image("https://example.org/a.svg")
    assert is_remote_image("  HTTP://example.org/a.png ")
    assert not is_remote_image("http://")
    assert not is_remote_image("images/a.png")
    assert not is_remote_image("ftp://example.org/a.png")


def test_bare_http_image_is_error_and_http_is_warning(tmp_path):
    f = quiz_file(tmp_path, questions=[{**QUESTION, "image": "http://"}])
    assert has(msgs(load_quiz(f)), "not a valid web address")
    f = quiz_file(tmp_path, questions=[{**QUESTION, "image": " http://example.org/a.png "}])
    result = load_quiz(f)
    assert result.errors == []
    assert has([str(w) for w in result.warnings], "http://", "https")
    assert result.quiz["questions"][0]["image"] == "http://example.org/a.png"


def test_whitespace_only_translation_falls_back_to_any(tmp_path):
    f = quiz_file(tmp_path, languages=["en", "it"], title={"any": "T", "it": "   "}, questions=[
        {"text": {"any": "Q"}, "options": [{"text": {"any": "A"}, "correct": True}, {"text": {"any": "B"}}]},
    ])
    result = load_quiz(f)
    assert result.errors == []
    assert result.quiz["title"] == {"en": "T", "it": "T"}
    f = quiz_file(tmp_path, languages=["en", "it"], title={"en": "T", "it": "  "}, questions=[
        {"text": {"any": "Q"}, "options": [{"text": {"any": "A"}, "correct": True}, {"text": {"any": "B"}}]},
    ])
    assert has(msgs(load_quiz(f)), "title", 'missing translation "it"')


def test_duplicate_keys_reported(tmp_path):
    f = raw_file(tmp_path, '{"title": "T", "questions": [{"text": "Q", "options": '
                           '[{"text": "A", "correct": true, "correct": false}, {"text": "B"}]}]}')
    assert has(msgs(load_quiz(f)), 'duplicate field "correct"')


def test_float_question_count_coerced(tmp_path):
    f = quiz_file(tmp_path, questions_per_quiz=1.0)
    quiz = load_quiz(f).quiz
    assert quiz["questions_per_quiz"] == 1 and isinstance(quiz["questions_per_quiz"], int)


def test_ui_non_string_value_message(tmp_path):
    f = quiz_file(tmp_path, languages=["en", "it"], ui={"start": {"en": 5}}, questions=[
        {"text": {"any": "Q"}, "options": [{"text": {"any": "A"}, "correct": True}, {"text": {"any": "B"}}]}])
    assert has(msgs(load_quiz(f)), "ui.start.en", "must be text")


def test_structural_failure_flag():
    assert load_quiz(FIX / "rule02-missing-title.json").structural_failure
    assert not load_quiz(FIX / "rule03-no-correct.json").structural_failure


def test_discover_problems(tmp_path):
    (tmp_path / "collection.json").write_text("{}")
    (tmp_path / ".hidden.json").write_text("{}")
    (tmp_path / "ok.json").write_text("{}")
    real = tmp_path / "real"
    real.mkdir()
    (real / "x.json").write_text("{}")
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    files, problems = discover(tmp_path)
    assert [p.name for p in files] == ["ok.json", "x.json"]
    assert len(problems) == 1 and "belongs inside a collection subfolder" in problems[0]


def test_collection_title_not_empty(tmp_path):
    f = raw_file(tmp_path, '{"title": ""}', "collection.json")
    assert has(msgs(load_collection(f)), "title", "must not be empty")


def test_monkeypatched_ui_languages(monkeypatch):
    monkeypatch.setattr(validate_mod, "ui_languages", lambda: {"en"})
    assert has(errors_of("rule09-unknown-ui-language.json"), "xx")
    assert load_quiz(FIX / "valid-minimal.json").errors == []


def test_author_schema_defs_identical():
    quiz = json.loads((Path(validate_mod.__file__).parent / "schema.json").read_text())
    coll = json.loads((Path(validate_mod.__file__).parent / "collection.schema.json").read_text())
    assert quiz["$defs"]["author"] == coll["properties"]["author"]


def test_ui_strings_languages_consistent():
    strings = validate_mod._ui_strings()
    placeholder = re.compile(r"\{(\w+)\}")

    def flat(d):
        return {k: v for k, v in d.items() if k != "messages"} | {
            f"messages.{k}": v for k, v in d.get("messages", {}).items()}

    en = flat(strings["en"])
    for lang, entry in strings.items():
        other = flat(entry)
        assert set(other) == set(en), lang
        for key in en:
            assert set(placeholder.findall(other[key])) == set(placeholder.findall(en[key])), (lang, key)
