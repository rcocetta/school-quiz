"""Site mode: turn a folder of quizzes into a static website (index pages, quiz pages, images).

The output mirrors the input folder: a quiz at `school/maths.json` becomes `school/maths.html`
and its local images keep their relative path. Everything is validated and every file path is
checked *before* anything is written, so a mistake never leaves half a site behind. (A real
disk failure while writing can still leave partial output.)
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from quizgen.build import (REPO_URL, BuildError, BuildResult, _asset, _env, _prepare, _rewrite_images,
                           _write_atomic, render_page)
from quizgen.validate import (Issue, ValidationResult, discover, is_remote_image, load_collection, load_quiz,
                              load_site, local_image_path, ui_strings)

DEFAULT_SITE_DIR = "site"
INDEX_CSP = "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'"


@dataclass
class _Quiz:
    path: Path
    data: dict  # normalised, author inheritance applied


@dataclass
class _Section:
    """One index page: the top of the site (`folder` is "") or a collection folder."""

    folder: str
    meta: dict  # site.json or collection.json (empty when there is none)
    lang: str
    quizzes: list[_Quiz] = field(default_factory=list)


@dataclass
class _Plan:
    """Every file to write, by path inside the output folder."""

    pages: dict[str, bytes] = field(default_factory=dict)
    images: dict[str, bytes] = field(default_factory=dict)

    def targets(self) -> list[str]:
        return [*self.pages, *self.images]


def build_site(quiz_dir: Path | str, out_dir: Path | str | None = None,
               questions_override: int | None = None) -> BuildResult:
    """Validate a folder of quizzes and write the site. Nothing is written when anything is wrong.

    Existing files in the output folder that the site does not need are left alone.
    """
    src = Path(quiz_dir)
    out = Path(out_dir) if out_dir else Path(DEFAULT_SITE_DIR)
    result = ValidationResult(None)

    def fail(message: str) -> BuildResult:
        result.errors.append(Issue("", "", message))
        return BuildResult(result)

    problem = _check_folders(src, out)
    if problem:
        return fail(problem)
    top, collections = _load_all(src, questions_override, result)
    if result.errors:
        return BuildResult(result)
    try:
        plan = _plan(top, collections)
    except BuildError as err:
        return fail(str(err))
    problem = _preflight(out, plan.targets())
    if problem:
        return fail(problem)
    try:
        _write(out, plan)
    except OSError as err:
        return fail(f"{out}: cannot write the site ({err.strerror or err})")
    return BuildResult(result, out, sum(len(s.quizzes) for s in (top, *collections)))


# --------------------------------------------------------------------------
# Step 1: input and output folders
# --------------------------------------------------------------------------


def _check_folders(src: Path, out: Path) -> str | None:
    """A message if the input/output pair is unusable, else None."""
    if not src.is_dir():
        return f"{src}: no such folder"
    try:
        if out.is_symlink():
            return f"{out}: the output folder is a link (symlink); choose a normal folder"
        if out.exists() and not out.is_dir():
            return f"{out}: the output must be a folder, but this is a file; choose another -o"
        if out.exists() and os.path.samefile(src, out):
            return f"{out}: the output folder must be different from the quiz folder; choose another -o"
        s, o = src.resolve(), out.resolve()
        if o.is_relative_to(s):
            return f"{out}: the output folder is inside the quiz folder; choose a folder outside it with -o"
        if s.is_relative_to(o):
            return f"{out}: the output folder contains the quiz folder; choose another -o"
    except (OSError, RuntimeError) as err:
        return f"{out}: cannot use this folder ({getattr(err, 'strerror', None) or err})"
    return None


# --------------------------------------------------------------------------
# Step 2: load and validate everything
# --------------------------------------------------------------------------


def _load_all(src: Path, override: int | None, result: ValidationResult) -> tuple[_Section, list[_Section]]:
    """Validate site.json, every collection.json and every quiz; issues go to `result`."""
    files, problems = discover(src)
    result.errors += [Issue("", "", p) for p in problems]

    def check(res: ValidationResult) -> dict:
        result.errors += res.errors
        result.warnings += res.warnings
        return res.quiz or {}

    site: dict = {}
    collection_meta: dict[str, dict] = {}
    quizzes: list[tuple[str, _Quiz]] = []
    for path in files:
        folder = "" if path.parent == src else path.parent.name
        if path.name == "site.json" and not folder:
            site = check(load_site(path))
        elif path.name == "collection.json":
            collection_meta[folder] = check(load_collection(path))
        else:
            data = check(load_quiz(path, override))
            if data:
                quizzes.append((folder, _Quiz(path, data)))

    site_lang = site.get("language", "en")
    top = _Section("", site, site_lang)
    sections = {name: _Section(name, collection_meta.get(name, {}), collection_meta.get(name, {}).get("language", site_lang))
                for name in sorted({f for f, _ in quizzes if f})}
    for name in set(collection_meta) - set(sections):
        result.warnings.append(Issue(str(src / name), "", "this collection has no quizzes, so it is skipped"))
    for folder, quiz in quizzes:
        section = sections[folder] if folder else top
        # D22/D27: a loose quiz may use the site author, a collection quiz only its collection's
        if "author" not in quiz.data and "author" in section.meta:
            quiz.data["author"] = section.meta["author"]
        section.quizzes.append(quiz)
    return top, list(sections.values())


# --------------------------------------------------------------------------
# Step 3: render every page in memory
# --------------------------------------------------------------------------


def _plan(top: _Section, collections: list[_Section]) -> _Plan:
    plan = _Plan()
    top_ui = ui_strings()[top.lang]
    collection_cards = []
    for sec in collections:
        cards = _add_quizzes(plan, sec)
        ui = ui_strings()[sec.lang]
        plan.pages[_join(sec.folder, "index.html")] = _render_index(
            lang=sec.lang, heading=sec.meta.get("title", sec.folder), description=sec.meta.get("description"),
            author=sec.meta.get("author"), back={"href": "../index.html", "text": ui["back_to_all"]},
            quizzes=cards, asset_base="../assets/")
        collection_cards.append({
            "href": quote(sec.folder) + "/index.html", "title": sec.meta.get("title", sec.folder),
            "description": sec.meta.get("description"),
            "count_text": _count_text(top_ui, "quizzes_count", len(cards)),
            "author_name": sec.meta.get("author", {}).get("name")})
    top_cards = _add_quizzes(plan, top)
    plan.pages["index.html"] = _render_index(
        lang=top.lang, heading=top.meta.get("title", top_ui["quizzes"]), description=top.meta.get("description"),
        author=top.meta.get("author"), collections=_sorted(collection_cards), quizzes=top_cards,
        empty_text=None if top_cards or collection_cards else top_ui["no_quizzes_yet"], asset_base="assets/")
    for name in ("quiz.css", "quiz.js"):
        plan.pages["assets/" + name] = _asset(name).encode("utf-8")
    plan.pages[".nojekyll"] = b""  # GitHub Pages would otherwise hide folders starting with "_"
    return plan


def _add_quizzes(plan: _Plan, sec: _Section) -> list[dict]:
    """Render the quiz pages of one section into the plan; return its (sorted) index cards."""
    ui_index = ui_strings()[sec.lang]
    asset_base = "../assets/" if sec.folder else "assets/"
    cards = []
    for q in sec.quizzes:
        quiz, ui = _prepare(q.data, sec.meta.get("ui"))
        try:
            _link_images(quiz, q.path.parent, sec.folder, plan.images)
        except BuildError as err:
            raise BuildError(f"{q.path}: {err}") from err
        html = render_page(quiz, ui, inline_assets=False, asset_base=asset_base, index_url="index.html")
        plan.pages[_join(sec.folder, q.path.stem + ".html")] = html.encode("utf-8")
        cards.append(_quiz_card(quiz, q.path.stem, ui_index))
    return _sorted(cards)


def _link_images(quiz: dict, base: Path, folder: str, images: dict[str, bytes]) -> None:
    """Queue each local image for copying (same relative path) and URL-encode its reference."""

    def link(ref: str) -> str:
        if is_remote_image(ref):
            return ref
        try:
            source = local_image_path(base, ref)
            if _join(folder, ref) not in images:
                images[_join(folder, ref)] = source.read_bytes()
        except ValueError as err:
            raise BuildError(str(err)) from err
        except OSError as err:
            raise BuildError(f'cannot read image "{ref}" ({err.strerror or err})') from err
        return quote(ref, safe="/")

    _rewrite_images(quiz, link)


def _quiz_card(quiz: dict, stem: str, ui: dict) -> dict:
    first = quiz["languages"][0]
    strings = ui_strings()
    return {
        "href": quote(stem) + ".html",
        "title": quiz["title"][first],
        "lang": first,
        "description": quiz.get("description", {}).get(first),
        "count_text": _count_text(ui, "questions_count", quiz["questions_per_quiz"]),
        "languages": [{"code": c, "flag": strings[c]["flag"], "name": strings[c]["name"]}
                      for c in quiz["languages"]],
        "author_name": quiz.get("author", {}).get("name"),
    }


def _render_index(*, lang: str, heading: str, description: str | None, author: dict | None,
                  asset_base: str, back: dict | None = None, collections: list[dict] | None = None,
                  quizzes: list[dict] | None = None, empty_text: str | None = None) -> bytes:
    ui = ui_strings()[lang]
    link = None
    if author:
        href = author.get("url") or ("mailto:" + author["email"] if "email" in author else None)
        link = {"text": ui["made_by"].format(name=author["name"]), "href": href,
                "external": bool(href and href.startswith(("http://", "https://")))}
    html = _env().get_template("index.html").render(
        lang=lang, page_title=heading, csp=INDEX_CSP, asset_base=asset_base,
        heading=heading, description=description, author=link, back=back,
        collections_heading=ui["collections"], collections=collections or [],
        quizzes_heading=ui["quizzes"], quizzes=quizzes or [], languages_label=ui["languages"],
        empty_text=empty_text, made_with={"text": ui["made_with"], "href": REPO_URL})
    return html.encode("utf-8")


def _count_text(ui: dict, key: str, count: int) -> str:
    """"5 quizzes", or the singular text ("1 quiz") when count is 1."""
    return ui[key + "_one"] if count == 1 else ui[key].format(count=count)


def _sorted(cards: list[dict]) -> list[dict]:
    """By title, ignoring case and accents."""
    def key(card: dict) -> str:
        plain = unicodedata.normalize("NFKD", card["title"])
        return "".join(c for c in plain if not unicodedata.combining(c)).casefold()
    return sorted(cards, key=key)


def _join(folder: str, name: str) -> str:
    return f"{folder}/{name}" if folder else name


# --------------------------------------------------------------------------
# Step 4: check the output folder, then write
# --------------------------------------------------------------------------


def _preflight(out: Path, targets: Iterable[str]) -> str | None:
    """A message naming what to rename or remove if any file could not be written, else None."""
    targets = list(dict.fromkeys(targets))
    by_key: dict[str, str] = {}
    folders: set[str] = set()
    for rel in targets:
        key = rel.casefold()  # case-insensitive disks (Windows, macOS) treat these as one file
        if key in by_key:
            return f'"{by_key[key]}" and "{rel}" would be the same file; rename one of them'
        by_key[key] = rel
        parts = rel.split("/")
        folders.update("/".join(parts[:i]).casefold() for i in range(1, len(parts)))
    for key in folders & by_key.keys():
        return f'"{by_key[key]}" is needed both as a file and as a folder; rename one of them'
    for rel in targets:
        current = out
        parts = rel.split("/")
        for i, part in enumerate(parts):
            current = current / part
            if current.is_symlink():
                return f"{current}: this is a link (symlink); remove it or choose another output folder"
            if not current.exists():
                break
            is_last = i == len(parts) - 1
            if is_last and current.is_dir():
                return f"{current}: this is a folder, but the site needs a file with this name; rename or remove it"
            if not is_last and not current.is_dir():
                return f"{current}: this is a file, but the site needs a folder with this name; rename or remove it"
    return None


def _write(out: Path, plan: _Plan) -> None:
    out.mkdir(parents=True, exist_ok=True)
    made: set[str] = set()
    for rel, data in {**plan.pages, **plan.images}.items():
        _make_folders(out, rel.split("/")[:-1], made)
        _write_atomic(out / rel, data)


def _make_folders(root: Path, parts: list[str], made: set[str]) -> None:
    """Create folders one level at a time, never through a link."""
    current = root
    for part in parts:
        current = current / part
        if str(current) in made:
            continue
        if current.is_symlink():
            raise OSError(f"{current} is a link")
        current.mkdir(exist_ok=True)
        made.add(str(current))
