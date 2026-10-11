"""Build the site that GitHub Pages serves from the ``docs/`` folder.

Run it from the repository root:

    python scripts/build_docs.py                  # project site: website/ at the root, quizzes at /quizzes/
    python scripts/build_docs.py --quizzes-only   # only your quizzes, at the root (for forks)
    python scripts/build_docs.py --check          # exit 1 if docs/ is out of date (CI runs this)

GitHub Pages is set to "Deploy from a branch": main, /docs. ``docs/`` is generated and
committed, so run this after changing ``quizzes/`` or ``website/`` and commit the result.

How it works: the whole site is built in a temporary folder first. If any quiz has an
error, nothing is touched and the errors are printed. Otherwise ``docs/`` is replaced.
``docs/.quizgen-build`` holds the mode ("project" or "quizzes-only"); it marks ``docs/`` as
generated, so a folder with other content is never wiped, and ``--check`` knows which
mode to rebuild. ``docs/.nojekyll`` stops GitHub from running Jekyll over the site.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from quizgen.cli import _print_issues
from quizgen.site import build_site

ROOT = Path(__file__).resolve().parent.parent
MARKER = ".quizgen-build"
MODES = ("project", "quizzes-only")
FIX = "python scripts/build_docs.py (or --quizzes-only)"


def build_into(out: Path, mode: str) -> bool:
    """Build the whole site into the empty folder `out`. Print problems; False on errors."""
    quizzes = ROOT / "quizzes"
    if mode == "project":
        website = ROOT / "website"
        if not website.is_dir():
            print("ERROR   website/ not found. Restore it, or use --quizzes-only.")
            return False
        shutil.copytree(website, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".DS_Store"))
        quiz_out = out / "quizzes"
    else:
        quiz_out = out
    built = build_site(quizzes, quiz_out)
    _print_issues(built.validation)
    if built.output is None:
        return False
    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / MARKER).write_text(mode + "\n", encoding="utf-8")
    return True


def read_tree(folder: Path) -> dict[str, bytes]:
    """Every file under `folder`: relative path -> contents."""
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def previous_mode(docs: Path) -> str | None:
    """The mode docs/ was built in, or None when there is no (valid) marker."""
    try:
        mode = (docs / MARKER).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return mode if mode in MODES else None


def can_replace(docs: Path) -> bool:
    """docs/ may be wiped when it does not exist, is empty, or is a previous build."""
    if docs.is_symlink() or (docs.exists() and not docs.is_dir()):
        return False
    return not docs.exists() or not any(docs.iterdir()) or previous_mode(docs) is not None


def run_build(mode: str) -> int:
    docs = ROOT / "docs"
    if not can_replace(docs):
        print(f"ERROR   {docs} has files that this script did not create, so it will not delete them.\n"
              f"        Move them somewhere else (or empty docs/), then run this again.")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "site"
        if not build_into(out, mode):
            print("\ndocs/ was not changed.")
            return 1
        if docs.exists():
            shutil.rmtree(docs)
        shutil.copytree(out, docs)
    print(f"built docs/ ({mode})")
    return 0


def run_check() -> int:
    docs = ROOT / "docs"
    mode = previous_mode(docs)
    if mode is None:
        print(f"docs/ is out of date: it is missing or was not built by this script — run: {FIX}")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "site"
        if not build_into(out, mode):
            return 1
        want, have = read_tree(out), read_tree(docs)
    differ = sorted(p for p in want.keys() | have.keys() if want.get(p) != have.get(p))
    if not differ:
        print(f"docs/ is up to date ({mode})")
        return 0
    print(f"docs/ is out of date — run: {FIX}")
    for path in differ:
        print(f"  {'missing' if path not in have else 'extra' if path not in want else 'changed'}: docs/{path}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the GitHub Pages site into docs/.")
    parser.add_argument("--quizzes-only", action="store_true",
                        help="publish only quizzes/, at the root of the site (no project website)")
    parser.add_argument("--check", action="store_true",
                        help="do not build; fail if docs/ is not what a build would produce")
    args = parser.parse_args(argv)
    if args.check:
        return run_check()
    return run_build("quizzes-only" if args.quizzes_only else "project")


if __name__ == "__main__":
    sys.exit(main())
