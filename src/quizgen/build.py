"""Build HTML quizzes from validated quiz files (single-file mode; site mode comes in Phase 3)."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from quizgen.validate import ANY, IMAGE_TYPES, Issue, ValidationResult, ui_strings, is_remote_image, load_quiz


@dataclass
class BuildResult:
    """`output` is None when nothing was written (see `validation.errors`)."""

    validation: ValidationResult
    output: Path | None = None


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

    quiz = copy.deepcopy(result.quiz)
    ui = merge_ui(quiz["languages"], quiz.pop("ui", {}))
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


def render_page(quiz: dict, ui: dict, *, inline_assets: bool, asset_base: str = "") -> str:
    """Render the quiz page from a normalised quiz (images already rewritten) and merged UI strings."""
    if not inline_assets:
        raise NotImplementedError("linked assets (site mode) arrive in Phase 3")
    css = _asset("quiz.css")
    js = _asset("quiz.js")
    first = quiz["languages"][0]
    return _env().get_template("quiz.html").render(
        lang=first,
        page_title=quiz["title"][first],
        csp=content_security_policy(css, js),
        inline_assets=True,
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
