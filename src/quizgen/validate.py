"""Load, validate and normalise quiz files (and collection.json files).

Every problem is collected as an `Issue` with a JSON path, so a creator can fix
everything in one go. On success `ValidationResult.quiz` holds the *normalised*
quiz: defaults filled in, every Text a full ``{lang: string}`` map.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ANY = "any"
DEFAULT_LANGUAGE = "en"
DEFAULT_QUESTIONS_PER_QUIZ = 10

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # per local image
# Local image types allowed in quizzes (D25) and their MIME types. Builders reuse this.
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


# --------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    file: str
    path: str
    message: str

    def __str__(self) -> str:
        where = f"{self.file}: {self.path}: " if self.path else f"{self.file}: "
        return where + self.message


@dataclass
class ValidationResult:
    """`quiz` is the normalised quiz (or collection data); None when there are errors."""

    quiz: dict | None
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    structural_failure: bool = False  # True when only the structure was checked


# --------------------------------------------------------------------------
# Resources
# --------------------------------------------------------------------------


@lru_cache(maxsize=None)
def _schema(name: str) -> dict:
    return json.loads((resources.files("quizgen") / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def ui_strings() -> dict:
    text = (resources.files("quizgen") / "ui_strings.json").read_text(encoding="utf-8")
    return json.loads(text)


def ui_languages() -> set[str]:
    """Language codes that have built-in interface strings (rule 9)."""
    return set(ui_strings())


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def load_quiz(path: Path | str, questions_override: int | None = None) -> ValidationResult:
    """Validate a quiz file and return it normalised."""
    return _load(Path(path), "schema.json",
                 lambda data, ctx: _check_quiz(data, ctx, questions_override))


def load_collection(path: Path | str) -> ValidationResult:
    """Validate a collection.json file (title, description, author)."""
    return _load(Path(path), "collection.schema.json", _check_collection)


def discover(directory: Path) -> tuple[list[Path], list[str]]:
    """Quiz and collection.json files in a folder plus one level of subfolders.

    Returns (files, problems). Hidden files/folders and symlinked folders are skipped;
    a collection.json at the top level is a problem (it belongs in a subfolder).
    """
    found: list[Path] = []
    problems: list[str] = []
    try:
        top = _json_files(directory)
        subfolders = sorted(p for p in directory.iterdir()
                            if p.is_dir() and not p.is_symlink() and not p.name.startswith("."))
    except OSError as exc:
        return [], [f"{directory}: cannot read folder ({exc.strerror or exc})"]
    for path in top:
        if path.name == "collection.json":
            problems.append(f"{path}: collection.json belongs inside a collection subfolder, not here")
        else:
            found.append(path)
    for sub in subfolders:
        try:
            found += _json_files(sub)
        except OSError as exc:
            problems.append(f"{sub}: cannot read folder ({exc.strerror or exc})")
    return found, problems


def _json_files(folder: Path) -> list[Path]:
    # "*.schema.json" (and schema.json) are JSON Schema files, not quizzes.
    return sorted(
        p for p in folder.glob("*.json")
        if p.is_file() and not p.name.startswith(".")
        and p.name != "schema.json" and not p.name.endswith(".schema.json")
    )


# --------------------------------------------------------------------------
# Loading + structural validation (rules 1-2)
# --------------------------------------------------------------------------


class _Ctx:
    """Collects issues for one file and holds per-quiz state."""

    def __init__(self, path: Path) -> None:
        self.file = str(path)
        self.base = path.parent
        self.errors: list[Issue] = []
        self.warnings: list[Issue] = []
        self.languages: list[str] = [DEFAULT_LANGUAGE]
        self.multi = False

    def error(self, path: str, message: str) -> None:
        self.errors.append(Issue(self.file, path, message))

    def warn(self, path: str, message: str) -> None:
        self.warnings.append(Issue(self.file, path, message))


def _load(path: Path, schema_name: str, check: Callable[[Any, _Ctx], dict | None]) -> ValidationResult:
    ctx = _Ctx(path)
    data = _read_json(path, ctx)
    structural = False
    if not ctx.errors:
        for jpath, message in _structural_issues(data, schema_name):
            ctx.error(jpath, message)
        structural = bool(ctx.errors)
    result = check(data, ctx) if not ctx.errors else None
    return ValidationResult(None if ctx.errors else result, ctx.errors, ctx.warnings, structural)


def _read_json(path: Path, ctx: _Ctx) -> Any:
    """Parse the file; problems go to ctx.errors (the caller checks that, not the return)."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            ctx.error("", f"file is too large (over {MAX_FILE_BYTES // (1024 * 1024)} MB)")
            return None
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        ctx.error("", f"cannot read file ({exc.strerror or exc})")
        return None
    except UnicodeDecodeError:
        ctx.error("", "the file is not valid UTF-8 text; save it as UTF-8")
        return None
    duplicates: list[str] = []
    try:
        data = json.loads(text, object_pairs_hook=lambda pairs: _object(pairs, duplicates))
    except json.JSONDecodeError as exc:
        ctx.error("", f"not valid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
        return None
    except (RecursionError, ValueError):
        ctx.error("", "the file is too deeply nested or contains a number that is too large")
        return None
    for name in dict.fromkeys(duplicates):
        ctx.error("", f'duplicate field "{name}": each field may appear only once in the same {{ ... }} block')
    try:
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    except (UnicodeEncodeError, RecursionError):
        ctx.error("", "the file contains an invalid character (a lone surrogate)")
    return data


def _object(pairs: list[tuple[str, Any]], duplicates: list[str]) -> dict:
    keys = [k for k, _ in pairs]
    duplicates.extend(k for k in keys if keys.count(k) > 1)
    return dict(pairs)


def _structural_issues(data: Any, schema_name: str) -> list[tuple[str, str]]:
    validator = Draft202012Validator(_schema(schema_name))
    issues: list[tuple[str, str]] = []
    for err in validator.iter_errors(data):
        issues.extend(_friendly(err))
    return issues


def _json_path(parts: Iterable[Any]) -> str:
    out = ""
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


_TYPE_NAMES = {
    "string": "text in quotes",
    "integer": "a whole number",
    "boolean": "true or false",
    "array": "a list [ ... ]",
    "object": "an object { ... }",
}


def _friendly(err: ValidationError) -> list[tuple[str, str]]:
    """Translate one jsonschema error into (json path, plain-language message) pairs."""
    path = list(err.absolute_path)
    where = _json_path(path)
    kind = err.validator
    if kind == "required":
        missing = [k for k in err.validator_value if k not in err.instance]
        return [(_json_path(path + [k]), f'missing required field "{k}"') for k in missing]
    if kind == "additionalProperties":
        known = list(err.schema.get("properties", {}))
        extra = [k for k in err.instance if k not in known]
        return [(_json_path(path + [k]), _unknown_field(k, known)) for k in extra]
    if kind == "type":
        wanted = err.validator_value
        names = [_TYPE_NAMES.get(t, t) for t in ([wanted] if isinstance(wanted, str) else wanted)]
        return [(where, "must be " + " or ".join(names))]
    if kind == "enum":
        options = ", ".join(f'"{v}"' for v in err.validator_value)
        return [(where, f"must be one of: {options}")]
    if kind == "minimum":
        return [(where, f"must be at least {err.validator_value}")]
    if kind == "minItems":
        return [(where, f"needs at least {err.validator_value} entries")]
    if kind in ("minProperties", "minLength"):
        return [(where, "must not be empty")]
    if kind == "uniqueItems":
        return [(where, "must not contain the same entry twice")]
    # oneOf is used only by the Text definition; check that, so a future oneOf
    # elsewhere falls through to jsonschema's own message instead of this one.
    if kind == "oneOf" and err.schema == _schema("schema.json")["$defs"]["text"]:
        return [(where, 'must be text in quotes, or a map of languages to text like {"en": "...", "it": "..."}')]
    return [(where, err.message)]


def _unknown_field(name: str, known: list[str]) -> str:
    guess = difflib.get_close_matches(name, known, n=1)
    hint = f' (did you mean "{guess[0]}"?)' if guess else ""
    return f'unknown field "{name}"{hint}'


# --------------------------------------------------------------------------
# Shared checks: author (rule 11), images (rule 10)
# --------------------------------------------------------------------------


def _check_author(author: dict, ctx: _Ctx, path: str) -> dict:
    """Rule 11. Returns the author with surrounding whitespace stripped."""
    out = {k: v.strip() for k, v in author.items()}
    if not out["name"]:
        ctx.error(f"{path}.name", "must not be empty")
    if "url" in out and not _is_web_url(out["url"]):
        ctx.error(f"{path}.url", 'must be a web address starting with "http://" or "https://"')
    if "email" in out and not _EMAIL_RE.fullmatch(out["email"]):
        ctx.error(f"{path}.email", 'must look like "name@example.org"')
    return out


def _is_web_url(value: str) -> bool:
    """http(s) URL with a host and no whitespace, control, zero-width or quote/bracket characters."""
    if any(c.isspace() or unicodedata.category(c) in ("Cc", "Cf") or c in '"<>`' for c in value):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return parts.scheme.lower() in ("http", "https") and bool(parts.netloc)


def is_remote_image(ref: str) -> bool:
    """True for a valid http(s) image URL (never copied or inlined); builders reuse this."""
    return _is_web_url(ref.strip())


def _check_image(value: str, ctx: _Ctx, path: str) -> str:
    """Rule 10 / D25. Returns the stripped reference. Remote URLs are not fetched (D6)."""
    value = value.strip()
    if is_remote_image(value):
        if value.lower().startswith("http://"):
            ctx.warn(path, "this image will not load: generated pages only allow https:// images, so use an https:// link")
    elif value.lower().startswith(("http://", "https://")):
        ctx.error(path, "this is not a valid web address for an image")
    else:
        _check_local_image(value, ctx, path)
    return value


def _check_local_image(value: str, ctx: _Ctx, path: str) -> None:
    windows_drive = bool(PureWindowsPath(value).drive)
    ext = os.path.splitext(value)[1].lower()
    if _SCHEME_RE.match(value) and not windows_drive:
        ctx.error(path, 'image must be a file next to the quiz or an "http(s)://" link')
    elif value.startswith(("/", "\\")) or PurePosixPath(value).is_absolute() or windows_drive:
        ctx.error(path, "image path must be relative to the quiz file, not absolute")
    elif ext not in IMAGE_TYPES:
        allowed = ", ".join(e.lstrip(".") for e in IMAGE_TYPES)
        hint = " Use a PNG, or link to the SVG with an https:// URL." if ext == ".svg" else ""
        ctx.error(path, f"local images must be one of: {allowed}.{hint}")
    else:
        try:
            if not _inside(ctx.base, value):
                ctx.error(path, 'image path must stay inside the quiz folder (no ".." or links going above it)')
            elif not (ctx.base / value).is_file():
                ctx.error(path, f'image file not found: "{value}" (paths are relative to the quiz file)')
            else:
                problem = _image_problem(ctx.base / value, ext)
                if problem:
                    ctx.error(path, problem)
        except (OSError, ValueError, RuntimeError):
            ctx.error(path, f'image file not found or invalid path: "{value}"')


def _image_problem(file: Path, ext: str) -> str | None:
    """Size and magic-byte check for a local image; None when fine."""
    try:
        if file.stat().st_size > MAX_IMAGE_BYTES:
            return (f"image is too large (over {MAX_IMAGE_BYTES // (1024 * 1024)} MB); "
                    "make it smaller, e.g. under 500 KB for quizzes")
        with file.open("rb") as handle:
            head = handle.read(12)
    except OSError:
        return "image file could not be read"
    if not _looks_like(head, ext):
        return f"this file is not a real {ext.lstrip('.').upper()} image (its content does not match its name)"
    return None


def _looks_like(head: bytes, ext: str) -> bool:
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"  # .webp


def _inside(base: Path, relative: str) -> bool:
    try:
        (base / relative).resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return True


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------


def _check_collection(data: dict, ctx: _Ctx) -> dict:
    """A collection does not know its quizzes' languages, so its `ui` values may be
    a string (stored as {"any": ...}) or a map with any known language."""
    out = {k: v for k, v in data.items() if k not in ("$schema", "ui")}
    if "author" in data:
        out["author"] = _check_author(data["author"], ctx, "author")
    if "ui" in data:
        out["ui"] = _check_ui(data["ui"], ctx, "ui", None)
    return out


# --------------------------------------------------------------------------
# Quiz: languages and Text (rules 6-9)
# --------------------------------------------------------------------------


def _setup_languages(data: dict, ctx: _Ctx) -> None:
    """Rules 8 and 9 (and reserved `any`); sets ctx.languages / ctx.multi."""
    ctx.multi = "languages" in data
    if ctx.multi and "language" in data:
        ctx.error("language", 'use either "language" (one language) or "languages" (several), not both')
    if ctx.multi:
        ctx.languages = list(data["languages"])
        codes = [(f"languages[{i}]", code) for i, code in enumerate(ctx.languages)]
    else:
        ctx.languages = [data.get("language", DEFAULT_LANGUAGE)]
        codes = [("language", ctx.languages[0])]
    ui_langs = ui_languages()
    for path, code in codes:
        if code == ANY:
            ctx.error(path, '"any" is reserved and cannot be a language code')
        elif code not in ui_langs:
            ctx.error(path, f'no built-in interface translation for "{code}" '
                            f'(available: {", ".join(sorted(ui_langs))})')


def _check_text(value: str | dict, ctx: _Ctx, path: str) -> dict[str, str] | None:
    """Rules 6 and 7: return the full {lang: string} map, or None after reporting."""
    if ctx.multi:
        if isinstance(value, str):
            ctx.error(path, 'plain text is not allowed when "languages" is set; write one text per language, '
                            'or use {"any": "..."} for text that is the same in every language')
            return None
        return _expand_map(value, ctx, path)
    if isinstance(value, dict):
        ctx.error(path, 'translations need a "languages" field at the top of the quiz, '
                        'e.g. "languages": ["en", "it"]; otherwise write plain text')
        return None
    if not value.strip():
        ctx.error(path, "text must not be empty")
        return None
    return {ctx.languages[0]: value}


def _expand_map(value: dict[str, str], ctx: _Ctx, path: str) -> dict[str, str] | None:
    allowed = set(ctx.languages) | {ANY}
    ok = True
    for key in value:
        if key not in allowed:
            ctx.error(f"{path}.{key}", f'unknown language "{key}" (this quiz uses: {", ".join(ctx.languages)})')
            ok = False
    expanded: dict[str, str] = {}
    fallback = value.get(ANY, "")
    for lang in ctx.languages:
        own = value.get(lang, "")
        text = own if own.strip() else fallback
        if text.strip():
            expanded[lang] = text
        else:
            ctx.error(path, f'missing translation "{lang}"')
            ok = False
    if ok and ANY in value and all(value.get(lang, "").strip() for lang in ctx.languages):
        ctx.warn(path, '"any" is never used because every language has its own text; remove it')
    return expanded if ok else None


# --------------------------------------------------------------------------
# Quiz: structure (rules 3-5, 10) and normalisation
# --------------------------------------------------------------------------


def _check_quiz(data: dict, ctx: _Ctx, override: int | None) -> dict:
    _setup_languages(data, ctx)
    out: dict[str, Any] = {"title": _check_text(data["title"], ctx, "title")}
    if "description" in data:
        out["description"] = _check_text(data["description"], ctx, "description")
    out["languages"] = ctx.languages
    out["ui"] = _check_ui(data.get("ui", {}), ctx, "ui", ctx.languages)
    out["questions_per_quiz"] = _check_question_count(data, ctx, override)
    out["feedback"] = data.get("feedback", "immediate")
    out["shuffle_options"] = data.get("shuffle_options", True)
    if "author" in data:
        out["author"] = _check_author(data["author"], ctx, "author")
    out["questions"] = [
        _check_question(q, ctx, f"questions[{i}]") for i, q in enumerate(data["questions"])
    ]
    return out


def _check_question_count(data: dict, ctx: _Ctx, override: int | None) -> int:
    """Rule 5 and the M == N warning. When M is not set anywhere it is min(10, N)."""
    total = len(data["questions"])
    wanted = override if override is not None else data.get("questions_per_quiz")
    if wanted is None:
        return min(DEFAULT_QUESTIONS_PER_QUIZ, total)
    wanted = int(wanted)  # the schema accepts 1.0 as an integer
    path = "" if override is not None else "questions_per_quiz"
    name = "--questions" if override is not None else "questions_per_quiz"
    if wanted < 1:
        ctx.error(path, f"{name} must be at least 1")
    elif wanted > total:
        ctx.error(path, f"{name} is {wanted} but the quiz only has {total} questions; "
                        "add questions or lower the number")
    elif wanted == total:
        ctx.warn(path, f"every attempt will use all {total} questions (same set, only the order changes)")
    return wanted


def _check_question(q: dict, ctx: _Ctx, path: str) -> dict:
    out: dict[str, Any] = {"text": _check_text(q["text"], ctx, f"{path}.text")}
    if "image" in q:
        out["image"] = _check_image(q["image"], ctx, f"{path}.image")
    _check_image_alt(q, out, ctx, path)
    if "explanation" in q:
        out["explanation"] = _check_text(q["explanation"], ctx, f"{path}.explanation")
    out["options"] = [
        _check_option(o, ctx, f"{path}.options[{j}]") for j, o in enumerate(q["options"])
    ]
    correct = sum(1 for o in q["options"] if o.get("correct", False))
    if correct != 1:
        ctx.error(f"{path}.options", f'exactly one option must have "correct": true (found {correct})')
    _warn_duplicates(out["options"], ctx, f"{path}.options")
    return out


def _check_option(o: dict, ctx: _Ctx, path: str) -> dict:
    out: dict[str, Any] = {}
    if "text" not in o and "image" not in o:
        ctx.error(path, 'an option needs a "text", an "image", or both')
    if "text" in o:
        out["text"] = _check_text(o["text"], ctx, f"{path}.text")
    if "image" in o:
        out["image"] = _check_image(o["image"], ctx, f"{path}.image")
    _check_image_alt(o, out, ctx, path)
    out["correct"] = o.get("correct", False)
    return out


def _check_image_alt(src: dict, out: dict, ctx: _Ctx, path: str) -> None:
    """`image_alt` describes the image for screen readers; it needs an image."""
    if "image_alt" not in src:
        return
    if "image" not in src:
        ctx.error(f"{path}.image_alt", 'an "image" is needed here: "image_alt" describes the image, so add an "image" or remove "image_alt"')
    else:
        out["image_alt"] = _check_text(src["image_alt"], ctx, f"{path}.image_alt")


def _warn_duplicates(options: list[dict], ctx: _Ctx, path: str) -> None:
    for lang in ctx.languages:
        seen: set[str] = set()
        reported: set[str] = set()
        for opt in options:
            text = (opt.get("text") or {}).get(lang)
            if text is None:
                continue
            key = text.strip().casefold()
            if key in seen and key not in reported:
                suffix = f" ({lang})" if ctx.multi else ""
                ctx.warn(path, f'duplicate option text "{text}"{suffix}')
                reported.add(key)
            seen.add(key)


# --------------------------------------------------------------------------
# `ui` overrides (rule 12, D24)
# --------------------------------------------------------------------------

_NOT_OVERRIDABLE = {"name", "flag"}
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _check_ui(ui: Any, ctx: _Ctx, path: str, quiz_langs: list[str] | None) -> dict:
    """Return overrides as {key: {lang: str}} (messages nested one level).

    `quiz_langs` is None for collection.json (language set unknown, strings -> "any").
    """
    builtin = ui_strings()[DEFAULT_LANGUAGE]
    if not isinstance(ui, dict):
        ctx.error(path, 'must be an object like {"start": "Go!"}')
        return {}
    out: dict[str, Any] = {}
    for key, value in ui.items():
        if key == "messages":
            out["messages"] = _check_ui_messages(value, ctx, f"{path}.messages", quiz_langs)
        elif key in _NOT_OVERRIDABLE or not isinstance(builtin.get(key), str):
            known = [k for k in builtin if k not in _NOT_OVERRIDABLE]
            ctx.error(f"{path}.{key}", _unknown_field(key, known).replace("field", "text key"))
        else:
            out[key] = _check_ui_value(value, builtin[key], ctx, f"{path}.{key}", quiz_langs)
    return out


def _check_ui_messages(value: Any, ctx: _Ctx, path: str, quiz_langs: list[str] | None) -> dict:
    messages = ui_strings()[DEFAULT_LANGUAGE]["messages"]
    if not isinstance(value, dict):
        ctx.error(path, 'must be an object like {"great": "..."}')
        return {}
    out = {}
    for key, text in value.items():
        if key not in messages:
            ctx.error(f"{path}.{key}", _unknown_field(key, list(messages)).replace("field", "message"))
        else:
            out[key] = _check_ui_value(text, messages[key], ctx, f"{path}.{key}", quiz_langs)
    return out


def _check_ui_value(value: Any, builtin: str, ctx: _Ctx, path: str, quiz_langs: list[str] | None) -> dict[str, str]:
    if isinstance(value, str) and not value.strip():
        ctx.error(path, "text must not be empty")
        return {}
    if isinstance(value, str):
        if ctx.multi:
            ctx.error(path, 'must be a map like {"en": "...", "it": "..."} when the quiz has "languages" '
                            '(use {"any": "..."} for every language)')
            return {}
        texts = {ANY if quiz_langs is None else quiz_langs[0]: value}
    elif isinstance(value, dict) and value:
        if quiz_langs is not None and not ctx.multi:
            ctx.error(path, 'translations need a "languages" field at the top of the quiz; otherwise write plain text')
            return {}
        allowed = set(quiz_langs) if quiz_langs is not None else ui_languages()
        texts = _ui_map(value, ctx, path, allowed)
    else:
        ctx.error(path, "must be text" + (" or a map of languages to text" if isinstance(value, dict) else ""))
        return {}
    for lang, text in texts.items():
        _check_placeholders(text, builtin, ctx, path if len(texts) == 1 else f"{path}.{lang}")
    return _expand_ui(texts, quiz_langs)


def _ui_map(value: dict, ctx: _Ctx, path: str, allowed_langs: set[str]) -> dict[str, str]:
    texts = {}
    for lang, text in value.items():
        if lang != ANY and lang not in allowed_langs:
            ctx.error(f"{path}.{lang}", f'unknown language "{lang}" (use: {", ".join(sorted(allowed_langs))})')
        elif not isinstance(text, str):
            ctx.error(f"{path}.{lang}", "must be text in quotes")
        elif not text.strip():
            ctx.error(f"{path}.{lang}", "text must not be empty")
        else:
            texts[lang] = text
    return texts


def _expand_ui(texts: dict[str, str], quiz_langs: list[str] | None) -> dict[str, str]:
    """Expand `any` over the quiz languages (own keys win); omitted languages stay absent."""
    if quiz_langs is None or ANY not in texts:
        return texts
    out = {lang: texts[ANY] for lang in quiz_langs}
    out.update({lang: t for lang, t in texts.items() if lang != ANY})
    return out


def _check_placeholders(text: str, builtin: str, ctx: _Ctx, path: str) -> None:
    wanted = set(_PLACEHOLDER_RE.findall(builtin))
    used = set(_PLACEHOLDER_RE.findall(text))
    for name in sorted(used - wanted):
        have = ", ".join("{%s}" % w for w in sorted(wanted)) or "none"
        ctx.error(path, f"{{{name}}} cannot be used here (this text can use: {have})")
    for name in sorted(wanted - used):
        ctx.warn(path, f"{{{name}}} from the original text is missing; the screen may look incomplete")
