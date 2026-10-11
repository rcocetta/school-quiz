"""Command line interface: `quizgen validate` and (later) `quizgen build`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quizgen.build import build_single
from quizgen.validate import ValidationResult, discover, load_collection, load_quiz


def _validate_file(path: Path) -> ValidationResult:
    return load_collection(path) if path.name == "collection.json" else load_quiz(path)


def _expand_inputs(inputs: list[str]) -> tuple[list[Path], list[str]]:
    """Turn files/directories into a list of files; also return missing-path messages."""
    files: list[Path] = []
    problems: list[str] = []
    for name in inputs:
        path = Path(name)
        if path.is_dir():
            found, dir_problems = discover(path)
            problems += dir_problems
            if not found and not dir_problems:
                print(f"note: no quiz files found in {path}")
            files += found
        elif path.is_file():
            files.append(path)
        else:
            problems.append(f"{name}: no such file or folder")
    return files, problems


def cmd_validate(args: argparse.Namespace) -> int:
    files, problems = _expand_inputs(args.input)
    for problem in problems:
        print(f"ERROR   {problem}")
    errors, warnings = len(problems), 0
    for path in files:
        result = _validate_file(path)
        errors += len(result.errors)
        warnings += len(result.warnings)
        _print_issues(result)
        if not result.errors and not result.warnings:
            print(f"ok      {path}")
    print(f"\n{len(files)} file(s) checked: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


def _print_issues(result: ValidationResult) -> None:
    for issue in result.errors:
        print(f"ERROR   {issue}")
    if result.structural_failure:
        print("        Fix these first: more checks will run once the structure is right.")
    for issue in result.warnings:
        print(f"warning {issue}")


def cmd_build(args: argparse.Namespace) -> int:
    path = Path(args.input)
    if path.is_dir():
        print("building a whole folder is not available yet (coming in a later version).\n"
              "Build one quiz file for now: quizgen build my-quiz.json", file=sys.stderr)
        return 2
    if not path.is_file():
        print(f"ERROR   {args.input}: no such file or folder")
        return 1
    built = build_single(path, args.output, args.questions)
    _print_issues(built.validation)
    if built.output is None:
        return 1
    print(f"built {built.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quizgen", description="Turn quiz JSON files into HTML quizzes.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="check quiz files and report problems")
    p_validate.add_argument("input", nargs="+", help="quiz .json files or folders")
    p_validate.set_defaults(func=cmd_validate)

    p_build = sub.add_parser("build", help="turn a quiz .json file into one self-contained HTML page")
    p_build.add_argument("input", help="a quiz .json file (folders come in a later version)")
    p_build.add_argument("-o", "--output", help="output .html file (default: next to the quiz)")
    p_build.add_argument("--questions", type=int, metavar="M", help="questions per attempt")
    p_build.set_defaults(func=cmd_build)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # never crash on odd characters or old consoles
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    args = build_parser().parse_args(argv)
    return args.func(args)
