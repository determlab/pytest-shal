"""Docs are tests (issue #34, D3): every command block on the first screen of
README.md and every command block in AGENTS.md is extracted and run as written,
in a fresh venv. A command that fails turns this red.

Needs network (pip against PyPI) like test_first_run.py. With env
RC_WHEELS=<dir> set, `pip install` lines run against that dir instead
(`--no-index --find-links`); a block marked `doc-test: skip` is skipped only
while RC_WHEELS is unset (shal#342 / PR 360).
"""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

import doc_extract

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
AGENTS = REPO / "AGENTS.md"


def readme_first_screen_units() -> list[doc_extract.Unit]:
    return doc_extract.extract_units(README, end_line=doc_extract.first_screen_end_line(README))


def agents_units() -> list[doc_extract.Unit]:
    return doc_extract.extract_units(AGENTS)


def make_venv(path: Path) -> Path:
    venv.create(path, with_pip=True)
    return path / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def run_units(units: list[doc_extract.Unit], py: Path, work: Path, *,
              repo: Path, rc_wheels: str | None = None) -> None:
    for unit in units:
        if unit.skip_reason and not rc_wheels:
            print(f"SKIPPED {unit.location()}: {unit.skip_reason}")
            continue
        if unit.kind == "file":
            (work / unit.filename).write_text(unit.text + "\n")
            continue
        for raw_line in unit.text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            argv = doc_extract.venv_argv(py, line, rc_wheels)
            cwd = repo if doc_extract.is_bare_pip_install_dot(line) else work
            out = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                  timeout=900, check=False)
            if out.returncode != 0:
                raise AssertionError(
                    f"{unit.location()}: {line}\n"
                    f"--- stdout ---\n{out.stdout}\n--- stderr ---\n{out.stderr}"
                )


# --- extraction correctness (fast, no subprocess) -------------------------

def test_readme_first_screen_extraction():
    units = readme_first_screen_units()
    shells = [u.text for u in units if u.kind == "shell"]
    files = [u for u in units if u.kind == "file"]
    assert any(s.split()[:2] == ["pip", "install"] for s in shells), shells
    assert any("--shal-setup sim" in s for s in shells), shells
    assert len(files) == 1 and files[0].filename == "test_first.py"
    assert "def test_room" in files[0].text
    # the two `shal records` output fences must not be picked up as commands
    assert not any("records in" in s for s in shells)


def test_agents_md_extraction():
    units = agents_units()
    shells = [u.text for u in units if u.kind == "shell"]
    files = [u for u in units if u.kind == "file"]
    assert len(files) == 1 and files[0].filename == "test_first.py"
    assert any("python -m pytest --shal-setup sim test_first.py" in s for s in shells)
    assert any("record.read" in s for s in shells)


def test_skip_count_capped_and_printed(capsys):
    skips = [u for u in (*readme_first_screen_units(), *agents_units()) if u.skip_reason]
    for s in skips:
        print(f"doc-test skip: {s.location()}: {s.skip_reason}")
    out = capsys.readouterr().out
    assert len(skips) <= doc_extract.SKIP_CAP, (
        f"too many doc-test skips ({len(skips)} > {doc_extract.SKIP_CAP}); "
        f"they must not grow silently:\n{out}"
    )


# --- deliberate failure: file:line in the message --------------------------

def test_bad_command_reports_file_and_line(tmp_path):
    bad_readme = tmp_path / "README.md"
    bad_readme.write_text(
        "# demo\n\n## Quick start\n\n```\npip install nonexistent-pkg-xyz\n```\n\n## Next\n"
    )
    units = doc_extract.extract_units(
        bad_readme, end_line=doc_extract.first_screen_end_line(bad_readme)
    )
    py = make_venv(tmp_path / "venv")
    work = tmp_path / "work"
    work.mkdir()

    try:
        run_units(units, py, work, repo=REPO)
    except AssertionError as exc:
        message = str(exc)
        assert f"{bad_readme}:5" in message
        assert "nonexistent-pkg-xyz" in message
    else:
        raise AssertionError("expected the bad pip install line to fail")


# --- real CLI, end to end ---------------------------------------------------

def test_real_docs_run_end_to_end(tmp_path):
    rc_wheels = os.environ.get("RC_WHEELS")
    py = make_venv(tmp_path / "venv")
    work = tmp_path / "work"
    work.mkdir()
    run_units(readme_first_screen_units(), py, work, repo=REPO, rc_wheels=rc_wheels)
    run_units(agents_units(), py, work, repo=REPO, rc_wheels=rc_wheels)


def test_mutated_command_fails_with_location(tmp_path):
    rc_wheels = os.environ.get("RC_WHEELS")
    py = make_venv(tmp_path / "venv")
    work = tmp_path / "work"
    work.mkdir()

    units = readme_first_screen_units()
    setup_units = [u for u in units if not (u.kind == "shell" and "--shal-setup sim" in u.text)]
    run_units(setup_units, py, work, repo=REPO, rc_wheels=rc_wheels)

    corrupted = next(u for u in units if u.kind == "shell" and "--shal-setup sim" in u.text)
    mutated = doc_extract.Unit(
        corrupted.path, corrupted.line, corrupted.kind,
        corrupted.text.replace("--shal-setup sim", "--shal-setup bogus-topology-xyz"),
    )

    try:
        run_units([mutated], py, work, repo=REPO, rc_wheels=rc_wheels)
    except AssertionError as exc:
        message = str(exc)
        assert mutated.location() in message
        assert "bogus-topology-xyz" in message
    else:
        raise AssertionError("expected the mutated --shal-setup value to fail")
