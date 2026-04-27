import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def iter_project_python_files():
    ignored_parts = {"__pycache__", ".pytest_cache", "tests"}
    for path in PROJECT_ROOT.rglob("*.py"):
        if any(part in ignored_parts for part in path.parts):
            continue
        yield path


def test_project_sources_parse_as_python36():
    failures = []
    for path in iter_project_python_files():
        source = path.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(path), feature_version=(3, 6))
        except SyntaxError as exc:
            failures.append(f"{path.relative_to(PROJECT_ROOT)}:{exc.lineno}: {exc.msg}")

    assert failures == []


def test_project_sources_avoid_python37_plus_typing_syntax():
    banned_patterns = [
        (re.compile(r"from __future__ import annotations"), "future annotations are not available on Python 3.6"),
        (re.compile(r"\b(list|dict|set|tuple)\s*\["), "PEP 585 builtin generic syntax is not Python 3.6 compatible"),
        (re.compile(r"->\s*[^:\n]+?\|"), "PEP 604 union return annotations are not Python 3.6 compatible"),
        (re.compile(r":\s*[^=\n]+?\|\s*None"), "PEP 604 union parameter annotations are not Python 3.6 compatible"),
        (re.compile(r"\.unlink\([^)]*missing_ok\s*="), "Path.unlink(missing_ok=...) is not Python 3.6 compatible"),
    ]
    failures = []

    for path in iter_project_python_files():
        source = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(source.splitlines(), start=1):
            for pattern, reason in banned_patterns:
                if pattern.search(line):
                    failures.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}: {reason}")

    assert failures == []
