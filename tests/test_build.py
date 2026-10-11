import base64
import hashlib
import json
from html import unescape
import re
import subprocess
import sys
from pathlib import Path

from quizgen.build import build_single, embed_json, merge_ui
from quizgen.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"

# smallest valid 1x1 PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
NASTY = "</script><script>alert(1)</script><!-- & \u2028 end"


def write_quiz(tmp_path, **overrides):
    data = {
        "title": "T",
        "questions": [{"text": "Q1", "options": [{"text": "A", "correct": True}, {"text": "B"}]},
                      {"text": "Q2", "options": [{"text": "A", "correct": True}, {"text": "B"}]}],
    }
    data.update(overrides)
    f = tmp_path / "q.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


def block(html, ident):
    m = re.search(rf'<script type="application/json" id="{ident}">(.*?)</script>', html, re.S)
    assert m, ident
    return json.loads(m.group(1))


def read(path):
    return Path(path).read_text(encoding="utf-8")


def test_build_writes_default_output_with_data(tmp_path):
    f = write_quiz(tmp_path)
    res = build_single(f)
    assert res.output == tmp_path / "q.html"
    html = read(res.output)
    quiz = block(html, "quiz-data")
    assert quiz["title"] == {"en": "T"} and len(quiz["questions"]) == 2
    assert "ui" not in quiz
    ui = block(html, "ui-strings")
    assert ui["en"]["start"] and ui["en"]["picture_n"] and ui["en"]["messages"]["great"]
    assert '<html lang="en">' in html


def test_local_image_becomes_data_uri(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(PNG)
    (tmp_path / "b.JPG").write_bytes(b"jpegbytes")
    f = write_quiz(tmp_path, questions=[{
        "text": "Q", "image": "images/a.png",
        "options": [{"image": "b.JPG", "correct": True},
                    {"text": "B", "image": "https://example.org/b.png"}]}])
    html = read(build_single(f).output)
    assert "images/a.png" not in html and "b.JPG" not in html
    q = block(html, "quiz-data")["questions"][0]
    assert q["image"] == "data:image/png;base64," + base64.b64encode(PNG).decode()
    assert q["options"][0]["image"] == "data:image/jpeg;base64," + base64.b64encode(b"jpegbytes").decode()
    assert q["options"][1]["image"] == "https://example.org/b.png"


def test_hostile_text_is_escaped_and_round_trips(tmp_path):
    f = write_quiz(tmp_path, title=NASTY, questions=[
        {"text": NASTY, "options": [{"text": NASTY, "correct": True}, {"text": "B"}]}])
    html = read(build_single(f).output)
    data_part = html.split('id="quiz-data">', 1)[1].split("</script>", 1)[0]
    assert "<" not in data_part and ">" not in data_part and "\u2028" not in data_part
    assert "<!--" not in data_part
    quiz = block(html, "quiz-data")
    assert quiz["title"]["en"] == NASTY
    assert quiz["questions"][0]["options"][0]["text"]["en"] == NASTY
    assert "<script>alert(1)" not in html  # page_title is autoescaped too
    assert html.count("</script>") == 3


def test_embed_json_escapes():
    assert embed_json({"a": "</script><!--&\u2029"}) == '{"a":"\\u003c/script\\u003e\\u003c!--\\u0026\\u2029"}'


def test_csp_hashes_match_inline_assets(tmp_path):
    html = read(build_single(write_quiz(tmp_path)).output)
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', html).group(1)
    csp = unescape(csp)
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    js = re.search(r"<script>(.*?)</script>", html, re.S).group(1)

    def h(text):
        return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"

    assert f"script-src {h(js)};" in csp and f"style-src {h(css)};" in csp
    assert "default-src 'none'" in csp and "img-src data: https:" in csp
    assert "http:" not in csp.replace("https:", "")


def test_times_tables_ui_merge(tmp_path):
    html = read(build_single(EXAMPLES / "times-tables.json", tmp_path / "t.html").output)
    ui = block(html, "ui-strings")
    assert list(ui) == ["en", "it", "fr"]
    assert ui["en"]["start"] == "Let's multiply!"
    assert ui["it"]["start"] == "Si parte!"
    from quizgen.validate import _ui_strings
    assert ui["fr"]["start"] == _ui_strings()["fr"]["start"]
    assert ui["fr"]["correct"] == "Excellent !"
    assert ui["en"]["correct"] == _ui_strings()["en"]["correct"]


def test_merge_ui_layers_and_messages():
    ui = merge_ui(["en", "it"],
                  {"start": {"en": "Go"}, "messages": {"great": {"en": "Wow", "it": "Wow!"}}},
                  {"start": {"any": "Collection"}, "next": {"any": "More"}})
    assert ui["en"]["start"] == "Go"            # quiz beats collection
    assert ui["it"]["start"] == "Collection"    # collection beats built-in
    assert ui["it"]["next"] == "More"
    assert ui["en"]["messages"]["great"] == "Wow"
    assert ui["en"]["messages"]["good"]         # untouched sub-key stays built-in


def test_questions_override(tmp_path):
    f = write_quiz(tmp_path)
    html = read(build_single(f, questions_override=1).output)
    assert block(html, "quiz-data")["questions_per_quiz"] == 1
    assert main(["build", str(f), "--questions", "2", "-o", str(tmp_path / "o.html")]) == 0
    assert block(read(tmp_path / "o.html"), "quiz-data")["questions_per_quiz"] == 2


def test_override_too_big_writes_nothing(tmp_path, capsys):
    f = write_quiz(tmp_path)
    assert main(["build", str(f), "--questions", "5"]) == 1
    assert not (tmp_path / "q.html").exists()
    assert "ERROR" in capsys.readouterr().out


def test_invalid_quiz_writes_nothing(tmp_path, capsys):
    f = write_quiz(tmp_path, questions=[{"text": "Q", "options": [{"text": "A"}, {"text": "B"}]}])
    out = tmp_path / "out" / "x.html"
    assert main(["build", str(f), "-o", str(out)]) == 1
    assert not out.exists() and not out.parent.exists()
    assert "exactly one option" in capsys.readouterr().out
    assert build_single(f).output is None
    assert list(tmp_path.glob("*.html")) == []


def test_warnings_printed_and_build_succeeds(tmp_path, capsys):
    f = write_quiz(tmp_path, questions_per_quiz=2)
    assert main(["build", str(f)]) == 0
    out = capsys.readouterr().out
    assert "warning" in out and f"built {tmp_path / 'q.html'}" in out


def test_directory_input_exits_2(tmp_path, capsys):
    assert main(["build", str(tmp_path)]) == 2
    assert "Phase 3" in capsys.readouterr().err


def test_missing_input_exits_1(tmp_path, capsys):
    assert main(["build", str(tmp_path / "nope.json")]) == 1


def test_image_alt_is_embedded(tmp_path):
    (tmp_path / "a.png").write_bytes(PNG)
    f = write_quiz(tmp_path, questions=[{
        "text": "Q", "image": "a.png", "image_alt": "A dot",
        "options": [{"text": "A", "correct": True}, {"text": "B"}]}])
    q = block(read(build_single(f).output), "quiz-data")["questions"][0]
    assert q["image_alt"] == {"en": "A dot"}


def test_python_dash_m_build_examples(tmp_path):
    for name in ("farm-animals", "times-tables"):
        out = tmp_path / f"{name}.html"
        proc = subprocess.run([sys.executable, "-m", "quizgen", "build", str(EXAMPLES / f"{name}.json"),
                               "-o", str(out)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert out.stat().st_size > 0
        assert f"built {out}" in proc.stdout
