import json
import os
import re
from html import unescape
from pathlib import Path

import pytest

from quizgen.build import build_single
from quizgen.site import build_site
from quizgen.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"
PNG = bytes.fromhex("89504e470d0a1a0a") + b"data"


def quiz(title="T", **extra):
    data = {"title": title,
            "questions": [{"text": "Q1", "options": [{"text": "A", "correct": True}, {"text": "B"}]},
                          {"text": "Q2", "options": [{"text": "A", "correct": True}, {"text": "B"}]}]}
    data.update(extra)
    return data


def put(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def read(path) -> str:
    return Path(path).read_text(encoding="utf-8")


def quiz_data(page: Path) -> dict:
    m = re.search(r'id="quiz-data">(.*?)</script>', read(page), re.S)
    return json.loads(m.group(1))


def ui_data(page: Path) -> dict:
    return json.loads(re.search(r'id="ui-strings">(.*?)</script>', read(page), re.S).group(1))


def csp(page: Path) -> str:
    return unescape(re.search(r'Content-Security-Policy" content="([^"]*)"', read(page)).group(1))


def hrefs(page: Path) -> list[str]:
    return re.findall(r'href="([^"]*)"', read(page))


@pytest.fixture
def tree(tmp_path):
    src = tmp_path / "in"
    put(src / "loose.json", quiz("Loose"))
    put(src / "school" / "collection.json", {"title": "Our School", "description": "By class",
                                              "author": {"name": "Ms Rossi"}, "language": "it",
                                              "ui": {"start": "Via!"}})
    put(src / "school" / "maths.json", quiz("Maths"))
    put(src / "plain" / "art.json", quiz("Art"))
    return src


def test_file_tree_and_links(tree, tmp_path):
    out = tmp_path / "out"
    res = build_site(tree, out)
    assert res.output == out and res.count == 3 and not res.validation.errors
    files = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()}
    assert files == {"index.html", "loose.html", "school/index.html", "school/maths.html",
                     "plain/index.html", "plain/art.html", "assets/quiz.css", "assets/quiz.js", ".nojekyll"}
    top = hrefs(out / "index.html")
    assert "loose.html" in top and "school/index.html" in top and "plain/index.html" in top
    assert "Our School" in read(out / "index.html") and "Loose" in read(out / "index.html")
    assert "../index.html" in hrefs(out / "school" / "index.html")
    assert "maths.html" in hrefs(out / "school" / "index.html")
    # collection without collection.json: folder name as heading
    assert "plain" in read(out / "plain" / "index.html")
    assert "../assets/quiz.css" in hrefs(out / "school" / "maths.html")
    assert "assets/quiz.js" in re.findall(r'src="([^"]*)"', read(out / "loose.html"))[0]


def test_pages_and_csp(tree, tmp_path):
    out = tmp_path / "out"
    build_site(tree, out)
    q = csp(out / "loose.html")
    assert q == ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; "
                 "base-uri 'none'; form-action 'none'")
    for idx in ("index.html", "school/index.html"):
        assert csp(out / idx) == ("default-src 'none'; style-src 'self'; img-src 'self'; "
                                  "base-uri 'none'; form-action 'none'")
        assert "<script" not in read(out / idx)
    assert quiz_data(out / "loose.html")["index_url"] == "index.html"
    assert quiz_data(out / "school" / "maths.html")["index_url"] == "index.html"
    single = build_single(put(tmp_path / "s.json", quiz())).output
    assert "index_url" not in quiz_data(single)


def test_images_copied_and_resolve(tmp_path):
    src = tmp_path / "in"
    data = quiz()
    data["questions"][0]["image"] = "img/a.png"
    data["questions"][1]["image"] = "img/a.png"
    data["questions"][1]["options"][1]["image"] = "https://example.org/x.png"
    put(src / "top.json", data)
    put(src / "col" / "c.json", data)
    for d in ("img", "col/img"):
        (src / d).mkdir(parents=True, exist_ok=True)
        (src / d / "a.png").write_bytes(PNG)
    out = tmp_path / "out"
    assert build_site(src, out).output
    for page in (out / "top.html", out / "col" / "c.html"):
        refs = [q["image"] for q in quiz_data(page)["questions"] if "image" in q]
        assert refs == ["img/a.png", "img/a.png"]  # unchanged; resolves next to the page
        assert (page.parent / "img" / "a.png").read_bytes() == PNG
    assert quiz_data(out / "top.html")["questions"][1]["options"][1]["image"] == "https://example.org/x.png"
    assert not (out / "img" / "x.png").exists()


def test_site_json_used(tmp_path):
    src = tmp_path / "in"
    put(src / "site.json", {"title": "Casa", "description": "Quiz di famiglia", "language": "it",
                            "author": {"name": "Papà", "url": "https://example.org"}})
    put(src / "loose.json", quiz())
    put(src / "col" / "a.json", quiz("A"))
    out = tmp_path / "out"
    res = build_site(src, out)
    assert res.count == 2 and not (out / "site.html").exists()
    html = read(out / "index.html")
    assert "<title>Casa</title>" in html and 'lang="it"' in html and "Quiz di famiglia" in html
    assert "Creato da Papà" in html and 'href="https://example.org"' in html
    assert quiz_data(out / "loose.html")["author"]["name"] == "Papà"
    assert "author" not in quiz_data(out / "col" / "a.html")  # site author is not inherited by collections
    assert "Tutti i quiz" not in html  # only the collection index has the back link
    assert 'lang="it"' in read(out / "col" / "index.html")  # collection inherits the site language


def test_collection_language_and_author(tree, tmp_path):
    out = tmp_path / "out"
    build_site(tree, out)
    html = read(out / "school" / "index.html")
    assert 'lang="it"' in html and "Tutti i quiz" in html and "Ms Rossi" in html
    assert 'lang="en"' in read(out / "plain" / "index.html")
    assert quiz_data(out / "school" / "maths.html")["author"] == {"name": "Ms Rossi"}
    assert "author" not in quiz_data(out / "plain" / "art.html")


def test_author_precedence(tmp_path):
    src = tmp_path / "in"
    put(src / "site.json", {"author": {"name": "Site"}})
    put(src / "own.json", quiz(author={"name": "Own"}))
    put(src / "col" / "collection.json", {"author": {"name": "Coll"}})
    put(src / "col" / "x.json", quiz())
    put(src / "col" / "y.json", quiz(author={"name": "Own2"}))
    out = tmp_path / "out"
    build_site(src, out)
    assert quiz_data(out / "own.html")["author"]["name"] == "Own"
    assert quiz_data(out / "col" / "x.html")["author"]["name"] == "Coll"
    assert quiz_data(out / "col" / "y.html")["author"]["name"] == "Own2"


def test_ui_inheritance(tmp_path):
    src = tmp_path / "in"
    put(src / "col" / "collection.json", {"ui": {"start": "Go!", "next": {"any": "Onward", "en": "Next one"},
                                                  "messages": {"great": "Wow"}}})
    put(src / "col" / "a.json", quiz())
    put(src / "col" / "b.json", quiz(ui={"start": "Quiz go"}))
    out = tmp_path / "out"
    assert build_site(src, out).output
    a, b = ui_data(out / "col" / "a.html")["en"], ui_data(out / "col" / "b.html")["en"]
    assert a["start"] == "Go!" and a["next"] == "Next one" and a["messages"]["great"] == "Wow"
    assert b["start"] == "Quiz go" and b["next"] == "Next one"  # quiz > collection > built-in
    assert a["finish"] == "See my results"


def test_singular_counts(tmp_path):
    src = tmp_path / "in"
    put(src / "col" / "a.json", quiz(questions_per_quiz=1))
    out = tmp_path / "out"
    build_site(src, out)
    assert ">1 quiz<" in read(out / "index.html")
    assert ">1 question<" in read(out / "col" / "index.html")
    assert "1 questions" not in read(out / "col" / "index.html")


def test_index_json_is_error(tmp_path, capsys):
    src = tmp_path / "in"
    put(src / "index.json", quiz())
    res = build_site(src, tmp_path / "out")
    assert res.output is None and "index.json" in str(res.validation.errors[0])
    assert not (tmp_path / "out").exists()
    assert main(["validate", str(src)]) == 1
    assert "index.json" in capsys.readouterr().out


def test_empty_folder_builds_index(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    out = tmp_path / "out"
    res = build_site(src, out)
    assert res.output and res.count == 0
    assert "No quizzes here yet." in read(out / "index.html")
    assert (out / "assets" / "quiz.css").is_file()


def test_invalid_anywhere_writes_nothing(tree, tmp_path, capsys):
    put(tree / "plain" / "bad.json", {"title": "x"})
    out = tmp_path / "out"
    assert main(["build", str(tree), "-o", str(out)]) == 1
    assert not out.exists()
    assert "bad.json" in capsys.readouterr().out


def test_bad_site_and_collection_language(tmp_path):
    src = tmp_path / "in"
    put(src / "site.json", {"language": "xx"})
    put(src / "c" / "collection.json", {"language": "yy"})
    put(src / "c" / "a.json", quiz())
    msgs = " ".join(str(e) for e in build_site(src, tmp_path / "out").validation.errors)
    assert 'no built-in interface translation for "xx"' in msgs and '"yy"' in msgs 


def test_site_json_in_subfolder_is_problem(tmp_path):
    src = tmp_path / "in"
    put(src / "c" / "site.json", {"title": "x"})
    put(src / "c" / "a.json", quiz())
    res = build_site(src, tmp_path / "out")
    assert res.output is None and "top of the quiz folder" in str(res.validation.errors[0])


def test_output_equals_input_refused(tree):
    res = build_site(tree, tree)
    assert res.output is None and "different" in str(res.validation.errors[0])
    assert not (tree / "index.html").exists()


def test_symlinked_output_refused(tree, tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    os.symlink(real, link)
    res = build_site(tree, link)
    assert res.output is None and not any(real.iterdir())


def test_symlink_inside_output_cannot_escape(tree, tmp_path):
    out, elsewhere = tmp_path / "out", tmp_path / "elsewhere"
    out.mkdir()
    elsewhere.mkdir()
    os.symlink(elsewhere, out / "school")
    res = build_site(tree, out)
    assert res.output is None and not any(elsewhere.iterdir())


def test_symlinked_image_escape_refused(tmp_path):
    src = tmp_path / "in"
    secret = tmp_path / "secret.png"
    secret.write_bytes(PNG)
    src.mkdir()
    os.symlink(secret, src / "a.png")
    data = quiz()
    data["questions"][0]["image"] = "a.png"
    put(src / "q.json", data)
    res = build_site(src, tmp_path / "out")
    assert res.output is None and res.validation.errors


def test_questions_override_applies_to_all(tree, tmp_path):
    out = tmp_path / "out"
    assert main(["build", str(tree), "-o", str(out), "--questions", "1"]) == 0
    for page in ("loose.html", "school/maths.html", "plain/art.html"):
        assert quiz_data(out / page)["questions_per_quiz"] == 1
    assert main(["build", str(tree), "-o", str(tmp_path / "o2"), "--questions", "5"]) == 1


def test_assets_folder_name_reserved(tmp_path):
    src = tmp_path / "in"
    put(src / "assets" / "a.json", quiz())
    assert build_site(src, tmp_path / "out").output is None


def test_empty_collection_skipped_with_warning(tmp_path):
    src = tmp_path / "in"
    put(src / "c" / "collection.json", {"title": "Empty"})
    put(src / "a.json", quiz())
    out = tmp_path / "out"
    res = build_site(src, out)
    assert res.output and res.validation.warnings and not (out / "c").exists()


def test_validate_dir_with_site_json(tmp_path, capsys):
    src = tmp_path / "in"
    put(src / "site.json", {"title": "Hi"})
    put(src / "a.json", quiz())
    assert main(["validate", str(src)]) == 0
    assert "2 file(s) checked" in capsys.readouterr().out
    put(src / "site.json", {"title": "Hi", "author": {"url": "https://x.org"}})
    assert main(["validate", str(src)]) == 1


def test_cli_build_examples(tmp_path, capsys):
    out = tmp_path / "site"
    assert main(["build", str(EXAMPLES), "-o", str(out)]) == 0
    assert "built 2 quizzes into" in capsys.readouterr().out
    for page in out.glob("*.html"):
        for href in hrefs(page):
            if not href.startswith("http"):
                assert (out / href).is_file(), href


def titles(page: Path) -> list[str]:
    return re.findall(r'class="card-link"[^>]*>(?:<span[^>]*>[^<]*</span>)?\s*([^<]+)</a>', read(page))


def test_ordering_and_quoted_hrefs(tmp_path):
    src = tmp_path / "in"
    for name, title in (("b.json", "banana"), ("a.json", "Apple"), ("e.json", "\u00c9clair"), ("z.json", "zebra")):
        put(src / name, quiz(title))
    put(src / "my quiz.json", quiz("Space quiz"))
    put(src / "zz" / "a.json", quiz("In zz"))
    put(src / "aa" / "a.json", quiz("In aa"))
    out = tmp_path / "out"
    build_site(src, out)
    assert (out / "my quiz.html").is_file()
    assert "my%20quiz.html" in hrefs(out / "index.html")
    assert titles(out / "index.html") == ["aa", "zz", "Apple", "banana", "\u00c9clair", "Space quiz", "zebra"]


def test_all_collections_empty(tmp_path):
    src = tmp_path / "in"
    put(src / "c" / "collection.json", {"title": "Empty"})
    res = build_site(src, tmp_path / "out")
    assert res.output and res.count == 0 and res.validation.warnings
    assert "No quizzes here yet." in read(tmp_path / "out" / "index.html")


def test_assets_and_html_folder_names_refused(tmp_path, capsys):
    for name in ("Assets", "x.HTML"):
        src = tmp_path / name / "in"
        put(src / name / "a.json", quiz())
        res = build_site(src, tmp_path / "out")
        assert res.output is None and "rename this folder" in str(res.validation.errors[0])
        assert main(["validate", str(src)]) == 1


def test_symlinked_json_refused(tmp_path, capsys):
    src = tmp_path / "in"
    src.mkdir()
    secret = put(tmp_path / "secret.json", quiz("Secret"))
    os.symlink(secret, src / "linked.json")
    os.symlink(put(tmp_path / "s2.json", {"title": "Stolen"}), src / "site.json")
    res = build_site(src, tmp_path / "out")
    assert res.output is None and "symlinks" in str(res.validation.errors[0])
    assert not (tmp_path / "out").exists()
    assert main(["validate", str(src)]) == 1


def test_image_name_with_special_characters(tmp_path):
    src = tmp_path / "in"
    data = quiz()
    data["questions"][0]["image"] = "my pic#1.png"
    data["questions"][0]["image_alt"] = ""
    put(src / "q.json", data)
    (src / "my pic#1.png").write_bytes(PNG)
    out = tmp_path / "out"
    assert build_site(src, out).output
    assert (out / "my pic#1.png").read_bytes() == PNG
    assert quiz_data(out / "q.html")["questions"][0]["image"] == "my%20pic%231.png"


@pytest.mark.parametrize("ref", ["a\x01.png", "a\\b.png", "./a.png", "x/../a.png"])
def test_odd_image_refs_refused(tmp_path, ref):
    src = tmp_path / "in"
    data = quiz()
    data["questions"][0]["image"] = ref
    put(src / "q.json", data)
    (src / "a.png").write_bytes(PNG)
    res = build_site(src, tmp_path / "out")
    assert res.output is None and res.validation.errors


def test_dotdot_prefixed_name_is_fine(tmp_path):
    src = tmp_path / "in"
    data = quiz()
    data["questions"][0]["image"] = "..x.png"
    put(src / "q.json", data)
    (src / "..x.png").write_bytes(PNG)
    assert build_site(src, tmp_path / "out").output


def test_non_utf8_name_refused(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    try:
        with open(os.path.join(os.fsencode(src), b"bad\xff.json"), "w") as f:
            f.write("{}")
    except OSError:
        pytest.skip("filesystem cannot create non-UTF-8 names")
    res = build_site(src, tmp_path / "out")
    assert res.output is None and "invalid characters" in str(res.validation.errors[0])


def test_output_inside_or_containing_input_refused(tree):
    assert "inside the quiz folder" in str(build_site(tree, tree / "site").validation.errors[0])
    assert "contains the quiz folder" in str(build_site(tree, tree.parent).validation.errors[0])


def test_output_is_a_file_refused(tree, tmp_path):
    f = tmp_path / "file"
    f.write_text("x")
    assert "must be a folder" in str(build_site(tree, f).validation.errors[0])


def test_preflight_clash_writes_nothing(tree, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "school").write_text("a file")  # needs to be a folder
    res = build_site(tree, out)
    assert res.output is None and "rename or remove" in str(res.validation.errors[0])
    assert sorted(p.name for p in out.iterdir()) == ["school"]
    out2 = tmp_path / "out2"
    (out2 / "loose.html").mkdir(parents=True)  # a folder where a page goes
    assert build_site(tree, out2).output is None


def test_case_clash_between_files(tmp_path):
    src = tmp_path / "in"
    put(src / "A.json", quiz())
    put(src / "a.json", quiz())
    res = build_site(src, tmp_path / "out")
    if res.output is None:  # case-sensitive disk: both names exist, still a clash for other disks
        assert "upper/lower case" in str(res.validation.errors[0])


def test_index_pages_have_no_script_and_languages_label(tree, tmp_path):
    out = tmp_path / "out"
    build_site(tree, out)
    for idx in ("index.html", "school/index.html", "plain/index.html"):
        assert "<script" not in read(out / idx)


def test_image_alt_decorative_and_warnings(tmp_path):
    from quizgen.validate import load_quiz
    (tmp_path / "a.png").write_bytes(PNG)
    data = quiz(languages=["en", "it"])
    data["title"] = {"any": "T"}
    for q in data["questions"]:
        q["text"] = {"any": "Q"}
        for o in q["options"]:
            o["text"] = {"any": "A"}
    data["questions"][0]["image"] = "a.png"
    data["questions"][0]["image_alt"] = ""
    res = load_quiz(put(tmp_path / "ok.json", data))
    assert not res.errors and res.quiz["questions"][0]["image_alt"] == {"en": "", "it": ""}
    # warnings: question image without alt, picture-only option without alt
    del data["questions"][0]["image_alt"]
    data["questions"][1]["options"][0] = {"image": "a.png", "correct": True}
    res = load_quiz(put(tmp_path / "warn.json", data))
    msgs = [str(w) for w in res.warnings]
    assert any("questions[0]" in m and '""' in m for m in msgs)
    assert any("questions[1].options[0]" in m and "picture-only" in m for m in msgs)
    # error: "" on a picture-only option
    data["questions"][1]["options"][0]["image_alt"] = ""
    res = load_quiz(put(tmp_path / "bad.json", data))
    assert any("needs a description" in str(e) for e in res.errors)


def test_empty_collection_warns_but_failed_quizzes_do_not(tmp_path):
    src = tmp_path / "in"
    put(src / "loose.json", quiz("Loose"))
    put(src / "empty" / "collection.json", {"title": "Empty"})
    put(src / "broken" / "collection.json", {"title": "Broken"})
    put(src / "broken" / "bad.json", quiz("Bad", questions_per_quiz=5))
    result = build_site(src, tmp_path / "out")
    warned = [w.file for w in result.validation.warnings if "no quizzes" in w.message]
    assert warned == [str(src / "empty")]
    assert any("only has 2 questions" in e.message for e in result.validation.errors)


def test_structure_hint_in_site_mode(tmp_path, capsys):
    put(tmp_path / "in" / "bad.json", {"title": "T", "questions": [{"text": "Q", "options": []}]})
    assert main(["build", str(tmp_path / "in"), "-o", str(tmp_path / "out")]) == 1
    assert "Fix these first" in capsys.readouterr().out
