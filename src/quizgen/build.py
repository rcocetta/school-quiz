"""Build HTML quizzes from validated quiz files: one self-contained file, or a whole site."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import posixpath
import tempfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from quizgen.validate import (ANY, IMAGE_TYPES, Issue, ValidationResult, _inside, discover, is_remote_image,
                              load_collection, load_quiz, load_site, ui_strings)

REPO_URL = "https://github.com/rcocetta/school-quiz"
DEFAULT_SITE_DIR = "site"
# Site mode: assets are linked from the same origin, so 'self' replaces the inline hashes.
QUIZ_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; "
            "base-uri 'none'; form-action 'none'")
INDEX_CSP = "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'"


@dataclass
class BuildResult:
    """`output` is None when nothing was written (see `validation.errors`).

    Site mode: `output` is the output folder and `count` the number of quiz pages written.
    """

    validation: ValidationResult
    output: Path | None = None
    count: int = 0


MAX_TOTAL_IMAGE_BYTES = 20 * 1024 * 1024  # all inlined images together, repeats counted


class BuildError(Exception):
    """A problem the creator can fix; the message is shown as-is."""


def build_single(quiz_path: Path | str, out_path: Path | str | None = None,
                 questions_override: int | None = None) -> BuildResult:
    """Validate one quiz file and write it as one self-contained HTML file.

    On any problem nothing is written and `output` is None (see `validation.errors`).
    Default output: `<stem>.html` next to the input. A folder (existing, or any path ending
    in "/") gets `<stem>.html` inside.
    """
    quiz_path = Path(quiz_path)
    result = load_quiz(quiz_path, questions_override)
    if result.errors:
        return BuildResult(result)
    out = Path(out_path) if out_path else quiz_path.with_suffix(".html")

    def fail(where: Path | str, message: str) -> BuildResult:
        result.errors.append(Issue(str(where), "", message))
        return BuildResult(result)

    try:
        if out.is_dir() or str(out_path).endswith(("/", os.sep)):
            out = out / (quiz_path.stem + ".html")
    except OSError as err:
        return fail(out, f"cannot write file ({err.strerror or err})")
    try:
        same = out.resolve() == quiz_path.resolve()
    except (OSError, RuntimeError):
        same = False
    if same:
        return fail(out, "the output would overwrite the quiz file; choose a different -o")

    quiz, ui = _prepare(result.quiz)
    try:
        _rewrite_images(quiz, _DataUriMaker(quiz_path.parent))
    except BuildError as err:
        return fail(quiz_path, str(err))
    html = render_page(quiz, ui, inline_assets=True)
    try:
        _write_atomic(out, html.encode("utf-8"))  # bytes: keeps the CSP hashes exact on every OS
    except OSError as err:
        return fail(out, f"cannot write file ({err.strerror or err})")
    return BuildResult(result, out)


def _prepare(quiz: dict, collection_ui: dict | None = None) -> tuple[dict, dict]:
    """Copy of a normalised quiz without its `ui`, plus the merged UI strings (both build modes)."""
    quiz = copy.deepcopy(quiz)
    return quiz, merge_ui(quiz["languages"], quiz.pop("ui", {}), collection_ui)


def render_page(quiz: dict, ui: dict, *, inline_assets: bool, asset_base: str = "",
                index_url: str | None = None) -> str:
    """Render the quiz page from a normalised quiz (images already rewritten) and merged UI strings.

    Linked mode (site): `asset_base` is the relative path to `assets/`; `index_url` (if given)
    lets the page link back to the index.
    """
    css = _asset("quiz.css") if inline_assets else ""
    js = _asset("quiz.js") if inline_assets else ""
    first = quiz["languages"][0]
    if index_url:
        quiz = {**quiz, "index_url": index_url}
    return _env().get_template("quiz.html").render(
        lang=first,
        page_title=quiz["title"][first],
        csp=content_security_policy(css, js) if inline_assets else QUIZ_CSP,
        inline_assets=inline_assets,
        asset_base=asset_base,
        css=Markup(css),
        js=Markup(js),
        quiz_json=Markup(embed_json(quiz)),
        ui_json=Markup(embed_json(ui)),
    )


def merge_ui(languages: list[str], quiz_ui: dict, collection_ui: dict | None = None) -> dict:
    """UI strings per language: built-in < collection `ui` < quiz `ui` (D24).

    Override maps are `{key: {lang_or_any: text}}`, `messages` nested one level. A language
    without an override keeps the lower layer's text.
    """
    builtin = ui_strings()
    ui = {lang: copy.deepcopy(builtin[lang]) for lang in languages}
    for layer in (collection_ui or {}, quiz_ui):
        for lang in languages:
            _apply(ui[lang], layer, lang)
    return ui


def _apply(target: dict, layer: dict, lang: str) -> None:
    for key, value in layer.items():
        if key == "messages":
            _apply(target["messages"], value, lang)
        elif lang in value:
            target[key] = value[lang]
        elif ANY in value:
            target[key] = value[ANY]


def embed_json(data: Any) -> str:
    """JSON that is safe inside a <script> element: no `<`, `>`, `&` or line-separator characters."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                          ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        text = text.replace(char, escaped)
    return text


def content_security_policy(css: str, js: str) -> str:
    """CSP for a page with exactly this inline CSS and JS; https images only (no http:)."""
    return (f"default-src 'none'; script-src {_hash(js)}; style-src {_hash(css)}; "
            "img-src data: https:; base-uri 'none'; form-action 'none'")


def _hash(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii") + "'"


def _rewrite_images(quiz: dict, fn: Callable[[str], str]) -> None:
    """Replace every question/option image reference with fn(ref)."""
    for question in quiz["questions"]:
        for item in (question, *question["options"]):
            if "image" in item:
                item["image"] = fn(item["image"])


class _DataUriMaker:
    """ref -> data: URI for local images (each file encoded once); remote URLs unchanged."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.cache: dict[str, str] = {}
        self.sizes: dict[str, int] = {}
        self.total = 0

    def __call__(self, ref: str) -> str:
        if is_remote_image(ref):
            return ref
        ext = os.path.splitext(ref)[1].lower()
        try:
            path = (self.base / ref).resolve()
            if ext not in IMAGE_TYPES or not path.is_relative_to(self.base.resolve()):
                raise BuildError(f'image is not allowed: "{ref}"')  # the validator already blocks this
            if ref not in self.cache:
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                self.cache[ref] = f"data:{IMAGE_TYPES[ext]};base64,{encoded}"
                self.sizes[ref] = len(encoded) * 3 // 4
        except (OSError, RuntimeError) as err:
            raise BuildError(f'cannot read image "{ref}" ({getattr(err, "strerror", None) or err})') from err
        self.total += self.sizes[ref]
        if self.total > MAX_TOTAL_IMAGE_BYTES:
            raise BuildError(f"the images add up to more than {MAX_TOTAL_IMAGE_BYTES // (1024 * 1024)} MB "
                             "(a picture used twice counts twice); use smaller images or https:// links")
        return self.cache[ref]


def _asset(name: str) -> str:
    text = (resources.files("quizgen") / "static" / name).read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n")  # browsers normalise newlines before hashing for the CSP


def _env() -> Environment:
    return Environment(loader=PackageLoader("quizgen", "templates"),
                       autoescape=select_autoescape(["html"]))


def _write_atomic(path: Path, data: bytes) -> None:
    """Write via a random exclusive temp file in the same folder, then rename into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".", suffix=".tmp", delete=False) as handle:
            tmp = Path(handle.name)
            handle.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Site mode
# --------------------------------------------------------------------------


@dataclass
class _Quiz:
    """A validated quiz plus where it goes: `folder` is "" (top) or the collection folder name."""

    path: Path
    folder: str
    data: dict  # normalised, author inheritance applied


def build_site(quiz_dir: Path | str, out_dir: Path | str | None = None,
               questions_override: int | None = None) -> BuildResult:
    """Validate a folder of quizzes and write a static site (index pages, quiz pages, images).

    The output mirrors the input folder: a quiz at `school/maths.json` becomes
    `school/maths.html`, so its local images keep the same relative path and need no rewriting.
    Nothing is written when anything is invalid; existing files in the output folder are kept.
    """
    src = Path(quiz_dir)
    out = Path(out_dir) if out_dir else Path(DEFAULT_SITE_DIR)
    result = ValidationResult(None)

    def fail(message: str) -> BuildResult:
        result.errors.append(Issue("", "", message))
        return BuildResult(result)

    try:
        if out.resolve() == src.resolve():
            return fail(f"{out}: the output folder must be different from the quiz folder; choose another -o")
        if out.is_symlink():
            return fail(f"{out}: the output folder is a link (symlink); choose a normal folder")
    except (OSError, RuntimeError) as err:
        return fail(f"{out}: cannot use this folder ({getattr(err, 'strerror', None) or err})")

    site, collections, quizzes = _load_all(src, questions_override, result)
    if result.errors:
        return BuildResult(result)
    site = site or {}
    site_lang = site.get("language", "en")

    pages: dict[str, bytes] = {}  # path inside the output folder -> content
    images: dict[str, Path] = {}  # path inside the output folder -> source file
    cards: dict[str, list[dict]] = {"": []}  # folder -> quiz cards of that index page
    for name in collections:
        cards[name] = []
    ui_index = {name: ui_strings()[(collections[name].get("language", site_lang) if name else site_lang)]
                for name in cards}
    for q in quizzes:
        coll = collections.get(q.folder, {})
        quiz, ui = _prepare(q.data, coll.get("ui"))
        stem = q.path.stem
        depth = "../" if q.folder else ""
        html = render_page(quiz, ui, inline_assets=False, asset_base=depth + "assets/", index_url="index.html")
        pages[_join(q.folder, stem + ".html")] = html.encode("utf-8")
        try:
            _collect_images(quiz, q, images)
        except BuildError as err:
            return fail(f"{q.path}: {err}")
        cards[q.folder].append(_quiz_card(quiz, stem, ui_index[q.folder]))

    collection_cards = []
    for name, coll in collections.items():
        lang = coll.get("language", site_lang)
        ui = ui_strings()[lang]
        title = coll.get("title", name)
        pages[_join(name, "index.html")] = _render_index(
            lang=lang, heading=title, description=coll.get("description"), author=coll.get("author"),
            back={"href": "../index.html", "text": ui_strings()[lang]["back_to_all"]},
            quizzes=_sorted(cards[name]), asset_base="../assets/")
        collection_cards.append({
            "href": quote(name) + "/index.html", "title": title, "description": coll.get("description"),
            "count_text": _count_text(ui_index[""], "quizzes_count", len(cards[name])),
            "author_name": coll.get("author", {}).get("name")})
    ui = ui_index[""]
    pages["index.html"] = _render_index(
        lang=site_lang, heading=site.get("title", ui["quizzes"]), description=site.get("description"),
        author=site.get("author"), collections=_sorted(collection_cards), quizzes=_sorted(cards[""]),
        empty_text=None if quizzes else ui["no_quizzes_yet"], asset_base="assets/")
    for name in ("quiz.css", "quiz.js"):
        pages["assets/" + name] = _asset(name).encode("utf-8")

    try:
        out.mkdir(parents=True, exist_ok=True)
        root = out.resolve()
        for rel, data in pages.items():
            _write_inside(root, rel, data)
        for rel, source in images.items():
            _write_inside(root, rel, source.read_bytes())
    except OSError as err:
        return fail(f"{out}: cannot write the site ({err.strerror or err})")
    return BuildResult(result, out, len(quizzes))


def _load_all(src: Path, override: int | None, result: ValidationResult
              ) -> tuple[dict | None, dict[str, dict], list[_Quiz]]:
    """Validate site.json, every collection.json and every quiz; collect all issues in `result`."""
    if not src.is_dir():
        result.errors.append(Issue("", "", f"{src}: no such folder"))
        return None, {}, []
    files, problems = discover(src)
    result.errors += [Issue("", "", p) for p in problems]

    def check(res: ValidationResult) -> dict | None:
        result.errors += res.errors
        result.warnings += res.warnings
        return res.quiz

    site = None
    collections: dict[str, dict] = {}
    found: list[_Quiz] = []
    for path in files:
        folder = "" if path.parent == src else path.parent.name
        if folder == "assets":
            result.errors.append(Issue("", "", f'{path}: the folder name "assets" is reserved for the page styles '
                                               "and scripts; rename the folder"))
        elif path.name == "site.json" and not folder:
            site = check(load_site(path))
        elif path.name == "collection.json" and folder:
            collections[folder] = check(load_collection(path)) or {}
        else:
            data = check(load_quiz(path, override))
            if data:
                found.append(_Quiz(path, folder, data))
    names = {q.folder for q in found if q.folder}
    for name in list(collections):
        if name not in names:
            result.warnings.append(Issue(str(src / name), "", "this collection has no quizzes, so it is skipped"))
            del collections[name]
    for name in names:
        collections.setdefault(name, {})  # a folder with quizzes but no collection.json
    # inheritance (D22/D27): a loose quiz may use the site author, a collection quiz only its collection's
    for q in found:
        fallback = site.get("author") if (site and not q.folder) else collections.get(q.folder, {}).get("author")
        if fallback and "author" not in q.data:
            q.data["author"] = fallback
    return site, dict(sorted(collections.items())), found


def _collect_images(quiz: dict, q: _Quiz, images: dict[str, Path]) -> None:
    """Find the local images of one quiz: output path -> source file (each once; stays inside the quiz folder)."""
    base = q.path.parent
    for question in quiz["questions"]:
        for item in (question, *question["options"]):
            ref = item.get("image")
            if ref is None or is_remote_image(ref):
                continue
            rel = posixpath.normpath(ref)
            if (os.path.splitext(rel)[1].lower() not in IMAGE_TYPES or rel.startswith("..")
                    or not _inside(base, ref)):  # the validator already blocks these
                raise BuildError(f'image is not allowed: "{ref}"')
            images[_join(q.folder, rel)] = base / ref


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
        quizzes_heading=ui["quizzes"], quizzes=quizzes or [], empty_text=empty_text,
        made_with={"text": ui["made_with"], "href": REPO_URL})
    return html.encode("utf-8")


def _count_text(ui: dict, key: str, count: int) -> str:
    """"5 quizzes", or the singular text ("1 quiz") when count is 1."""
    return ui[key + "_one"] if count == 1 else ui[key].format(count=count)


def _sorted(cards: list[dict]) -> list[dict]:
    return sorted(cards, key=lambda c: c["title"].casefold())


def _join(folder: str, name: str) -> str:
    return f"{folder}/{name}" if folder else name


def _write_inside(root: Path, rel: str, data: bytes) -> None:
    """Write `rel` below the (resolved) output folder; refuse if a link would lead outside it."""
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.parent.resolve().is_relative_to(root):
        raise OSError(f"{rel} would be written outside the output folder")
    _write_atomic(target, data)
