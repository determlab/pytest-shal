"""Extract runnable units from a markdown doc's fenced code blocks (issue #34).

A unit is either a **file** (an unlabeled or `python`-labeled fence whose first
line is a `# name.py` comment — the doc's own convention for naming the file it
wants on disk before the next command runs) or a **shell** block (a `bash`/`sh`
fence, or an unlabeled fence whose first line starts with a recognised command).
Anything else — prose, an output fence, a snippet with no filename comment — is
not a unit and is skipped.

A `<!-- doc-test: skip <reason> -->` line immediately before a fence marks that
block's unit to be skipped. Per the shal model (shal#342 / PR 360) this applies
only while `RC_WHEELS` is unset: a block marked skip because it needs a release
newer than what PyPI has must still run once `RC_WHEELS` points at the
release-candidate wheels, so the D2 run covers it.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

SHELL_COMMANDS = {"pip", "pip3", "python", "python3", "pytest", "ruff", "mypy", "git", "gh"}

SKIP_CAP = 2  # shal PR 360 started at 4; the CTO asked for 2 (issue #34).

_FENCE_RE = re.compile(r"^```([\w+-]*)\s*$")
_SKIP_RE = re.compile(r"<!--\s*doc-test:\s*skip\s+(.+?)\s*-->")
_PY_FILE_RE = re.compile(r"^#\s*([\w./-]+\.py)\s*$")


@dataclass(frozen=True)
class Unit:
    path: Path
    line: int  # 1-indexed line of the opening fence
    kind: str  # "file" or "shell"
    text: str
    filename: str | None = None  # set when kind == "file"
    skip_reason: str | None = None

    def location(self) -> str:
        return f"{self.path}:{self.line}"


def _is_shell_text(text: str) -> bool:
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        first = shlex.split(line, comments=True)
        return bool(first) and first[0] in SHELL_COMMANDS
    return False


def first_screen_end_line(path: Path) -> int | None:
    """1-indexed line of the first `##` heading after the quick-start `##`.

    The quick start is the file's first `##` heading; the first screen runs up
    to (not including) the next one. None means the whole file is one screen.
    """
    headings = [i + 1 for i, line in enumerate(path.read_text().splitlines())
                if line.startswith("## ")]
    return headings[1] if len(headings) >= 2 else None


def extract_units(path: Path, *, end_line: int | None = None) -> list[Unit]:
    """Fenced blocks of `path`, in document order, as runnable Units.

    `end_line` (1-indexed, exclusive) limits extraction to a leading slice of
    the file, for README's first-screen rule.
    """
    lines = path.read_text().splitlines()
    if end_line is not None:
        lines = lines[: end_line - 1]

    units: list[Unit] = []
    pending_skip: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        skip_match = _SKIP_RE.search(line)
        if skip_match:
            pending_skip = skip_match.group(1).strip()
            i += 1
            continue
        fence = _FENCE_RE.match(line)
        if not fence:
            if line.strip():
                pending_skip = None  # a marker must directly precede its fence
            i += 1
            continue

        lang = fence.group(1)
        start_line = i + 1
        body_start = i + 1
        j = body_start
        while j < len(lines) and lines[j].strip() != "```":
            j += 1
        text = "\n".join(lines[body_start:j])

        first_text_line = text.splitlines()[0] if text.splitlines() else ""
        py_file = _PY_FILE_RE.match(first_text_line.strip())
        if py_file:
            units.append(Unit(path, start_line, "file", text, filename=py_file.group(1),
                               skip_reason=pending_skip))
        elif lang in ("bash", "sh") or (lang == "" and _is_shell_text(text)):
            units.append(Unit(path, start_line, "shell", text, skip_reason=pending_skip))
        pending_skip = None
        i = j + 1

    return units


def adapt_pip_install(line: str, rc_wheels: str | None) -> str:
    """Point a `pip install` line at the RC wheel dir instead of PyPI."""
    if not rc_wheels:
        return line
    tokens = shlex.split(line, comments=True)
    if tokens and tokens[0] in ("pip", "pip3") and len(tokens) > 1 and tokens[1] == "install":
        return f"{line} --no-index --find-links {rc_wheels}"
    return line


def venv_argv(py: Path, line: str, rc_wheels: str | None = None) -> list[str]:
    """The line's tokens, rewritten to invoke the given venv's interpreter."""
    line = adapt_pip_install(line, rc_wheels)
    tokens = shlex.split(line, comments=True)
    if not tokens:
        return []
    cmd, rest = tokens[0], tokens[1:]
    if cmd in ("pip", "pip3"):
        return [str(py), "-m", "pip", *rest]
    if cmd in ("python", "python3"):
        return [str(py), *rest]
    if cmd == "pytest":
        return [str(py), "-m", "pytest", *rest]
    return [cmd, *rest]


def is_bare_pip_install_dot(line: str) -> bool:
    """True for the doc's own `pip install .` (run from the checkout, not a temp dir)."""
    tokens = shlex.split(line, comments=True)
    return tokens[:3] == ["pip", "install", "."]
