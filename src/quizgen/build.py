"""Build HTML quizzes from validated quiz files (single-file mode; site mode comes in Phase 3)."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from quizgen.validate import ANY, IMAGE_TYPES, ValidationResult, _ui_strings, is_remote_image, load_quiz


@dataclass
class BuildResult:
    """`output` is None when nothing was written (see `validation.errors`)."""

    validation: ValidationResult
    output: Path | None = None


def build_single(quiz_path: Path | str, out_path: Path | str | None = None,
                 questions_override: int | None = None) -> BuildResult:
    """Validate one quiz file and write it as one self-contained HTML file.

    On any validation error nothing is written. Default output: `<stem>.html` next to the input.
    """
    quiz_path = Path(quiz_path)
    result = load_quiz(quiz_path, questions_override)
    if result.errors:
        return BuildResult(result)
    out_path = Path(out_path) if out_path else quiz_path.with_suffix(".html")

    quiz = copy.deepcopy(result.quiz)
    ui = merge_ui(quiz["languages"], quiz.pop("ui", {}))
    _inline_images(quiz, quiz_path.parent)

    css = _asset("quiz.css")
    js = _asset("quiz.js")
    first = quiz["languages"][0]
    html = _env().get_template("quiz.html").render(
        lang=first,
        page_title=quiz["title"][first],
        csp=content_security_policy(css, js),
        inline_assets=True,
        css=Markup(css),
        js=Markup(js),
        quiz_json=Markup(embed_json(quiz)),
        ui_json=Markup(embed_json(ui)),
    )
    _write_atomic(out_path, html.encode("utf-8"))  # bytes: keeps the CSP hashes exact on every OS
    return BuildResult(result, out_path)


def merge_ui(languages: list[str], quiz_ui: dict, collection_ui: dict | None = None) -> dict:
    """UI strings per language: built-in < collection `ui` < quiz `ui` (D24).

    Override maps are `{key: {lang_or_any: text}}`, `messages` nested one level. A language
    without an override keeps the lower layer's text.
    """
    builtin = _ui_strings()
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


def _inline_images(quiz: dict, base: Path) -> None:
    for question in quiz["questions"]:
        for item in (question, *question["options"]):
            if "image" in item:
                item["image"] = _image_ref(item["image"], base)


def _image_ref(ref: str, base: Path) -> str:
    if is_remote_image(ref):
        return ref
    ext = os.path.splitext(ref)[1].lower()
    path = (base / ref).resolve()
    if ext not in IMAGE_TYPES or not path.is_relative_to(base.resolve()):
        raise ValueError(f"image is not allowed: {ref}")  # the validator already blocks this
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{IMAGE_TYPES[ext]};base64,{data}"


def _asset(name: str) -> str:
    return (resources.files("quizgen") / "static" / name).read_bytes().decode("utf-8")


def _env() -> Environment:
    return Environment(loader=PackageLoader("quizgen", "templates"),
                       autoescape=select_autoescape(["html"]))


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
