"""scripts/build_docs.py: builds docs/ for GitHub Pages and checks that it is up to date."""

import importlib.util
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_docs", REPO / "scripts" / "build_docs.py")
build_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_docs)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A small repository: one quiz and a one-page website."""
    shutil.copytree(REPO / "examples", tmp_path / "quizzes")
    (tmp_path / "website" / "assets").mkdir(parents=True)
    (tmp_path / "website" / "index.html").write_text("<!doctype html><title>Home</title>", encoding="utf-8")
    (tmp_path / "website" / "assets" / "site.css").write_text("body{}", encoding="utf-8")
    monkeypatch.setattr(build_docs, "ROOT", tmp_path)
    return tmp_path


def test_project_mode(repo):
    assert build_docs.main([]) == 0
    docs = repo / "docs"
    assert (docs / "index.html").read_text(encoding="utf-8").startswith("<!doctype html><title>Home")
    assert (docs / "assets" / "site.css").is_file()
    assert (docs / "quizzes" / "index.html").is_file()
    assert (docs / ".nojekyll").is_file()
    assert (docs / ".quizgen-build").read_text(encoding="utf-8").strip() == "project"


def test_quizzes_only_mode(repo):
    assert build_docs.main(["--quizzes-only"]) == 0
    docs = repo / "docs"
    assert (docs / "index.html").read_text(encoding="utf-8") != "<!doctype html><title>Home</title>"
    assert "Home" not in (docs / "index.html").read_text(encoding="utf-8")
    assert not (docs / "quizzes").exists()
    assert not (docs / "assets" / "site.css").exists()
    assert (docs / ".nojekyll").is_file()
    assert (docs / ".quizgen-build").read_text(encoding="utf-8").strip() == "quizzes-only"


def test_rebuild_replaces_old_files(repo):
    build_docs.main([])
    (repo / "docs" / "old.html").write_text("x", encoding="utf-8")
    assert build_docs.main([]) == 0
    assert not (repo / "docs" / "old.html").exists()


def test_refuses_to_wipe_docs_it_did_not_build(repo, capsys):
    (repo / "docs").mkdir()
    (repo / "docs" / "notes.txt").write_text("mine", encoding="utf-8")
    assert build_docs.main([]) == 1
    assert (repo / "docs" / "notes.txt").read_text(encoding="utf-8") == "mine"
    assert "will not delete" in capsys.readouterr().out


def test_empty_docs_is_fine(repo):
    (repo / "docs").mkdir()
    assert build_docs.main([]) == 0


def test_errors_leave_docs_untouched(repo, capsys):
    build_docs.main([])
    before = build_docs.read_tree(repo / "docs")
    (repo / "quizzes" / "broken.json").write_text("{}", encoding="utf-8")
    assert build_docs.main([]) == 1
    assert "ERROR" in capsys.readouterr().out
    assert build_docs.read_tree(repo / "docs") == before


def test_check_passes_after_build(repo):
    build_docs.main([])
    assert build_docs.main(["--check"]) == 0
    build_docs.main(["--quizzes-only"])
    assert build_docs.main(["--check"]) == 0  # detects the mode from the marker


def test_check_fails_after_quiz_edit(repo, capsys):
    build_docs.main([])
    quiz = next((repo / "quizzes").glob("farm-animals.json"))
    quiz.write_text(quiz.read_text(encoding="utf-8").replace('"Farm Animals"', '"Farm Friends"', 1), encoding="utf-8")
    assert build_docs.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "out of date" in out and "python scripts/build_docs.py" in out
    assert "docs/quizzes/farm-animals.html" in out


def test_check_fails_without_a_build(repo):
    assert build_docs.main(["--check"]) == 1


def test_build_is_deterministic(repo):
    build_docs.main([])
    first = build_docs.read_tree(repo / "docs")
    build_docs.main([])
    assert build_docs.read_tree(repo / "docs") == first

