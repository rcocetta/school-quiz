import json
import shutil
import subprocess
import sys
from pathlib import Path

from quizgen.cli import main

FIX = Path(__file__).parent / "fixtures"
EXAMPLES = Path(__file__).parent.parent / "examples"


def test_validate_examples_ok(capsys):
    assert main(["validate", str(EXAMPLES)]) == 0
    assert "0 error(s)" in capsys.readouterr().out


def test_validate_bad_file_exits_1(capsys):
    assert main(["validate", str(FIX / "rule03-no-correct.json")]) == 1
    out = capsys.readouterr().out
    assert "ERROR" in out and "questions[0].options" in out


def test_validate_warnings_exit_0(capsys):
    assert main(["validate", str(FIX / "warn-m-equals-n.json")]) == 0
    assert "warning" in capsys.readouterr().out


def test_validate_missing_path_exits_1(capsys):
    assert main(["validate", "nope.json"]) == 1


def test_validate_directory_with_collections(tmp_path, capsys):
    sub = tmp_path / "school"
    sub.mkdir()
    shutil.copy(FIX / "valid-minimal.json", tmp_path / "top.json")
    shutil.copy(FIX / "valid-minimal.json", sub / "inner.json")
    shutil.copy(FIX / "collection-valid.json", sub / "collection.json")
    assert main(["validate", str(tmp_path)]) == 0
    assert "3 file(s) checked" in capsys.readouterr().out
    (sub / "collection.json").write_text(json.dumps({"author": {"url": "https://x.org"}}))
    assert main(["validate", str(tmp_path)]) == 1



def test_python_dash_m():
    proc = subprocess.run([sys.executable, "-m", "quizgen", "validate", str(EXAMPLES)],
                          capture_output=True, text=True)
    assert proc.returncode == 0
